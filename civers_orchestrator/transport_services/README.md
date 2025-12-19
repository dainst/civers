# Transport Services

Message transport layer for the orchestrator, providing a clean separation between business logic and message-broker specifics.

## Overview

The transport layer is responsible for all external communication. It acts as a "shell" that:

1. **Listens** for external requests (Kafka topics).
2. **Translates** transport-agnostic instructions from the Orchestrator into transport-specific events.
3. **Publishes** events to appropriate service topics.
4. **Handles** deserialization and validation of incoming messages.

**Key Principle:** The transport layer contains **ZERO** business logic. It only knows how to move data and translate types.

## Structure

```text
transport_services/
├── transport_service_interface.py  # Abstract interface for any transport
├── kafka/                          # Kafka-specific implementation
│   ├── kafka_transport_service.py  # Main transport service (The "Worker")
│   ├── event_models.py             # Core Kafka event Pydantic models
│   ├── event_publisher.py          # Resilient message publishing logic
│   ├── event_registry.py           # Dynamic lookup of event models by name
│   └── external_events/            # Event models for external CIVERS components
└── adapters/
    ├── transport_adapter_interface.py  # Mapping interface (Component -> Topic)
    └── kafka_adapter.py                # Implementation using configuration mappings
```

## Transport Interface

All transport implementations must implement `TransportServiceInterface`:

| Method | Purpose |
|--------|---------|
| `start()` | Initialize connections, start background consumer tasks |
| `stop()` | Gracefully close connections and flush producers |
| `register_handler()` | Register async callback for a specific channel/topic |
| `send_response()` | Send a validated message to a destination |
| `health_check()` | Verify broker connectivity and API versions |

## Kafka Implementation

### KafkaTransportService

The "Brain" of the transport layer. It runs an `asyncio` loop that:

- **Consumes** from multiple topics defined in `testing.yaml` or `kafka.yaml`.
- **Deserializes** JSON safely (resilient to malformed payloads).
- **Delegates** processing to `OrchestratorService`.
- **Executes** returned `WorkflowTransition` objects by publishing new Kafka events.

### Event Registry & Models

The system uses a dynamic `EventRegistry` to map string names to Pydantic classes. This allows the `KafkaTransportAdapter` to return the name of a model (e.g., `"ArchiveRequestEvent"`) and the transport to instantiate it correctly.

All events inherit from [BaseModel](https://docs.pydantic.dev/latest/concepts/models/) for:

- Automatic validation of incoming payloads.
- Strict typing of outgoing data.
- JSON serialization/deserialization.

### Component Mappings (Configuration Driven)

Mappings are defined in `configs/data/defaults/kafka.yaml`. The adapter uses these to know where to send requests for each component.

```yaml
# Precise dictionary format used in config
component_mappings:
  archive_generator:
    request_topic: "archive.requests"
    response_topics:
      success: "archive.completed"
      failure: "archive.failed"
    event_models:
      request: "ArchiveRequestEvent"
      success: "ArchiveCompletedEvent"
      failure: "ArchiveFailedEvent"

  metadata_extractor:
    request_topic: "metadata.extraction.requests"
    response_topics:
      success: "metadata.extraction.completed"
      failure: "metadata.extraction.failed"
    event_models:
      request: "MetadataExtractionRequestEvent"
      success: "MetadataExtractionCompletedEvent"
      failure: "MetadataExtractionFailedEvent"
```

## Event Flow

1. **Orchestrator** determines next step and returns: `StepInstruction(component="archive_generator", ...)`.
2. **KafkaTransportService** passes this to `KafkaTransportAdapter.translate_instruction()`.
3. **Adapter** looks up the mapping and returns a dictionary with the target **topic** and **event model name**.
4. **Transport** uses `EventRegistry` to find the Pydantic model.
5. **EventPublisher** sends the validated message to Kafka.

## Resilience & Quality of Service

- **Safe Deserialization**: Uses `_safe_json_deserializer` to prevent consumer crashes on bad JSON.
- **Unique Group IDs**: Uses randomly generated or unique `group_id` for test environments to avoid rebalancing delays.
- **Offset Management**: Configurable `auto_offset_reset` (defaulting to `earliest` in tests) to ensure no events are missed.

## Testing

The transport layer is designed to be fully mockable. Use the `MockTransport` in unit tests to verify orchestrator behavior without needing Docker or Kafka.

For integration and E2E testing, a real `KafkaTransportService` is used alongside a `live_kafka_service` fixture which starts a background worker.
