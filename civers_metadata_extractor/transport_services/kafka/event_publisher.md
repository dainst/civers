# EventPublisher Documentation

## Purpose

The EventPublisher class provides essential event publishing functionality for the metadata extraction workflow, focusing on MVP requirements only. It handles publishing events to Kafka topics with proper error handling and topic routing.

## Key Methods

### `__init__(connection_manager, topics)`
- **Purpose**: Initialize the event publisher with connection manager and topic mapping
- **Parameters**: 
  - `connection_manager`: Kafka connection manager for producer access
  - `topics`: Dictionary mapping event types to topic names
- **Usage**: 
  ```python
  publisher = EventPublisher(connection_manager, topics)
  ```

### `publish_extraction_completed(event)`
- **Purpose**: Publish metadata extraction completion event to Kafka
- **Parameters**: `event` (MetadataExtractionCompletedEvent) - Completion event to publish
- **Returns**: `bool` - True if published successfully, False otherwise
- **Usage**:
  ```python
  success = await publisher.publish_extraction_completed(completion_event)
  ```

### `publish_extraction_failed(event)`
- **Purpose**: Publish metadata extraction failure event to Kafka  
- **Parameters**: `event` (MetadataExtractionFailedEvent) - Failure event to publish
- **Returns**: `bool` - True if published successfully, False otherwise
- **Usage**:
  ```python
  success = await publisher.publish_extraction_failed(failure_event)
  ```

### `publish_workflow_progress(event)`
- **Purpose**: Publish workflow progress event to track extraction stages
- **Parameters**: `event` (WorkflowProgressEvent) - Progress event to publish  
- **Returns**: `bool` - True if published successfully, False otherwise
- **Usage**:
  ```python
  success = await publisher.publish_workflow_progress(progress_event)
  ```

### `_publish_event(topic, key, event_data)`
- **Purpose**: Core event publishing method handling Kafka producer interaction
- **Parameters**: 
  - `topic` (str) - Kafka topic to publish to
  - `key` (str) - Message key for partitioning  
  - `event_data` (Dict) - Event data as dictionary
- **Returns**: `bool` - True if published successfully, False otherwise

## Function Signature Changes

### Extracted Methods
- **Old Signature**: `KafkaTransportService._publish_metadata_extraction_completed(event)`
- **New Signature**: `EventPublisher.publish_extraction_completed(event)`
- **Reason**: Extracted to separate publishing concerns from main transport service
- **Call Sites Updated**: WorkflowOrchestrator completion handling

- **Old Signature**: `KafkaTransportService._publish_metadata_extraction_failed(event)`  
- **New Signature**: `EventPublisher.publish_extraction_failed(event)`
- **Reason**: Extracted to separate publishing concerns from main transport service
- **Call Sites Updated**: WorkflowOrchestrator error handling

- **Old Signature**: `KafkaTransportService._publish_event(topic, key, event_data)`
- **New Signature**: `EventPublisher._publish_event(topic, key, event_data)`  
- **Reason**: Extracted core publishing logic as private method
- **Call Sites Updated**: All internal publishing methods

### New Methods
- **New Signature**: `EventPublisher.get_supported_events()` - Returns list of supported event types
- **New Signature**: `EventPublisher.get_topic_mapping()` - Returns current topic configuration
- **Reason**: Added for introspection and configuration visibility

## Integration Points

### WorkflowOrchestrator Integration
The EventPublisher integrates with WorkflowOrchestrator for publishing workflow events:
```python
# In WorkflowOrchestrator.__init__
self.event_publisher = event_publisher

# Publishing completion events
await self.event_publisher.publish_extraction_completed(completion_event)

# Publishing failure events  
await self.event_publisher.publish_extraction_failed(failure_event)

# Publishing progress updates
await self.event_publisher.publish_workflow_progress(progress_event)
```

### KafkaConnectionManager Integration
EventPublisher depends on KafkaConnectionManager for producer access:
```python
# EventPublisher uses connection manager's producer
if not self.connection_manager.producer:
    logger.error("❌ Kafka producer not initialized") 
    return False

future = self.connection_manager.producer.send(topic=topic, key=key, value=event_data)
```

### Topic Configuration Integration
EventPublisher uses topic mapping for flexible routing:
```python
topics = {
    'metadata_extraction_completed': 'metadata.extraction.completed',
    'metadata_extraction_failed': 'metadata.extraction.failed', 
    'workflow_progress': 'metadata.workflow.progress'
}
publisher = EventPublisher(connection_manager, topics)
```

## Usage Examples

### Basic EventPublisher Setup
```python
from transport_services.kafka.event_publisher import EventPublisher

# Initialize with connection manager and topics
publisher = EventPublisher(
    connection_manager=kafka_connection_manager,
    topics={
        'metadata_extraction_completed': 'metadata.completed',
        'metadata_extraction_failed': 'metadata.failed',
        'workflow_progress': 'workflow.progress'
    }
)
```

### Publishing Completion Event
```python
from transport_services.kafka.event_models import MetadataExtractionCompletedEvent

# Create completion event
completion_event = MetadataExtractionCompletedEvent(
    request_id="req-123",
    url="https://example.com",
    extracted_metadata={"title": "Example"},
    domain_used="example.com",
    mappers_used=["JsonLDMapper"],
    processing_time_seconds=1.5,
    artifacts_created=["output.json"],
    total_fields_extracted=1
)

# Publish the event
success = await publisher.publish_extraction_completed(completion_event)
if success:
    print("✅ Completion event published")
else:
    print("❌ Failed to publish completion event")
```

### Error Handling Example
```python
try:
    success = await publisher.publish_extraction_failed(failure_event)
    if not success:
        logger.warning("Event publishing failed but extraction continues")
except Exception as e:
    logger.error(f"Unexpected error in event publishing: {e}")
```

### Topic Fallback Configuration
```python
# EventPublisher supports topic fallbacks for backward compatibility
topics = {
    'metadata_extracted': 'legacy.metadata.extracted',  # Legacy topic name
    'metadata_extraction_failed': 'metadata.extraction.failed'
}

# Will use 'legacy.metadata.extracted' as fallback for completion events
publisher = EventPublisher(connection_manager, topics)
```

The EventPublisher provides a clean, focused interface for publishing essential events while maintaining backward compatibility and proper error handling for production use.