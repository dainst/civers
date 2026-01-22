# Workflow Monitoring Plan

This plan outlines the implementation of a unified Kafka monitoring tool to track and debug requests across the CIVERS workflow.

## 1. Objectives

The goal is to create a centralized monitoring utility that provides visibility into the end-to-end request lifecycle, specifically tracking:

- **Sender**: The component that initiated a request or event.
- **Receiver**: The component that consumed and is processing the event.
- **Metadata Sent**: The payload and metadata associated with each step.
- **Request Flow**: A visual/textual representation of the request moving through different services.

## 2. Architecture

The monitor is a standalone Python utility located at `scripts/kafka_flow_monitor.py` that acts as a "passive observer" on the Kafka bus.

### Key Components

- **Multi-Topic Consumer**: Listens to ALL relevant topics defined in `configs/defaults/kafka.yaml`.
- **State Tracker**: Correlates events using `request_id` to build a complete picture of the request journey.
- **Payload Inspector**: Extracts and formats human-readable metadata from each message.
- **Real-time Logger**: Outputting a structured timeline of events.

## 3. Targeted Topics

The monitor will subscribe to the following topic patterns:

- `orchestrator.*` (Requests, Status, Completion)
- `metadata.*` (Requests, Status, Completion)
- `archive.*` (Requests, Status, Completion)
- `doi.*` (Requests, Status, Completion)

## 4. Implementation Details

### A. Sender & Receiver Identification

Since Kafka messages don't always explicitly state "sender" and "receiver" in the payload, the monitor will infer them based on the topic:

- **`*.requests`**: Sender = Producer (usually Orchestrator), Receiver = Target Service (e.g., Metadata Extractor).
- **`*.status` / `*.completed`**: Sender = Processing Service, Receiver = Orchestrator/Status Listeners.

### B. Metadata Tracking

For each message, the monitor will display:

1. **Event Type**: (e.g., `ArchiveRequest`, `MetadataExtractionCompleted`)
2. **Request ID**: To correlate with other events.
3. **Core Payload**: URL, Status, etc.
4. **Metadata Field**: The contents of the `metadata` dictionary in the event models.
5. **Headers**: Any Kafka headers (if used for tracing).

### C. Monitoring Tool Features

- **Live Tail**: Real-time stream of events with color-coded status (✅ Success, ❌ Failure, ⏳ Processing).
- **Request History**: Look back at previous messages (within the Kafka retention period).
- **Trace View**: Grouping events by `request_id` to show the sequence.
- **Verbose Mode**: Print raw JSON payload for deep debugging.

## 5. Usage

To run the monitor locally:

```bash
python3 scripts/kafka_flow_monitor.py
```

Make sure you have `aiokafka` and `pyyaml` installed in your environment.

## 6. Implementation Notes

The current version in `scripts/kafka_flow_monitor.py` implements:

- **Multi-topic subscription**: Listens to all orchestrator, metadata, archive, and DOI topics.
- **Inference Engine**: Automatically identifies **Sender** and **Receiver** based on topic names.
- **Metadata Inspection**: Pretty prints the `metadata` payload from events.
- **Visual Feedback**: Uses ANSI colors to highlight successes, failures, and request types.

## 7. Review of Existing Tools

- `civers_metadata_extractor/scripts/kafka_monitor.py`: Provides a good template for async consumption and stats.
- `civers_archive_generator/transport_services/kafka/monitor_app.py`: Simple implementation using `kafka-python`, but we prefer `aiokafka` for consistency with newer components.
