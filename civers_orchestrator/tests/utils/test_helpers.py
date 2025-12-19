"""Test utilities for transport-agnostic testing.

These helpers create test data without Kafka-specific coupling,
enabling testing of the refactored transport-agnostic architecture.

Usage:
    from tests.utils.test_helpers import create_transport_agnostic_instruction

    instruction = create_transport_agnostic_instruction(
        component="archive_generator",
        input_data={"url": "https://example.com"}
    )
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


# Temporary transport-agnostic StepInstruction model
# This mirrors the NEW format that will be created in Task 13
@dataclass
class TransportAgnosticStepInstruction:
    """
    Transport-agnostic step instruction (NEW format for Task 13+).

    This is what StepInstruction will look like after refactoring.
    Used in tests to validate adapter translations.
    """
    request_id: str
    url: str
    component: str  # Component identifier (not topic!)
    input_schema: str  # Schema name (not event model!)
    input_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None
    step_config: Optional[Any] = None  # Will be WorkflowStepConfig


def create_transport_agnostic_instruction(
    request_id: str = "test-001",
    url: str = "https://example.com",
    component: str = "test_component",
    input_schema: str = "TestRequest",
    input_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> TransportAgnosticStepInstruction:
    """
    Create a transport-agnostic StepInstruction for testing.

    This creates instructions in the NEW format (component, schema)
    instead of the old format (topic, event_model).

    Args:
        request_id: Unique request identifier
        url: URL being processed
        component: Component identifier (e.g., "archive_generator")
        input_schema: Data schema name (e.g., "ArchiveRequest")
        input_data: Additional data fields

    Returns:
        TransportAgnosticStepInstruction instance

    Example:
        >>> instruction = create_transport_agnostic_instruction(
        ...     component="archive_generator",
        ...     input_schema="ArchiveRequest",
        ...     input_data={"priority": 1}
        ... )
        >>> assert instruction.component == "archive_generator"
        >>> assert not hasattr(instruction, "input_topic")
    """
    if input_data is None:
        input_data = {}

    return TransportAgnosticStepInstruction(
        request_id=request_id,
        url=url,
        component=component,
        input_schema=input_schema,
        input_data=input_data,
        metadata=metadata
    )


def create_mock_component_mapping(
    component: str,
    request_topic: str,
    success_topic: str,
    failure_topic: str,
    request_event: str,
    success_event: str,
    failure_event: str
) -> Dict[str, Any]:
    """
    Create mock component mapping for Kafka adapter tests.

    Returns mapping structure expected by KafkaTransportAdapter.

    Args:
        component: Component identifier
        request_topic: Kafka topic for requests
        success_topic: Kafka topic for successful responses
        failure_topic: Kafka topic for failed responses
        request_event: Event model name for requests
        success_event: Event model name for success
        failure_event: Event model name for failure

    Returns:
        Dictionary with Kafka component mapping structure

    Example:
        >>> mapping = create_mock_component_mapping(
        ...     component="archive_generator",
        ...     request_topic="archive.requests",
        ...     success_topic="archive.completed",
        ...     failure_topic="archive.failed",
        ...     request_event="ArchiveRequestEvent",
        ...     success_event="ArchiveCompletedEvent",
        ...     failure_event="ArchiveFailedEvent"
        ... )
        >>> assert mapping["request_topic"] == "archive.requests"
    """
    return {
        "request_topic": request_topic,
        "response_topics": {
            "success": success_topic,
            "failure": failure_topic
        },
        "event_models": {
            "request": request_event,
            "success": success_event,
            "failure": failure_event
        }
    }


def assert_kafka_operation(
    operation: Dict[str, Any],
    expected_topic: str,
    expected_event_model: str,
    expected_request_id: str
):
    """
    Assert that a Kafka operation dict has expected structure.

    Used to verify adapter.translate_instruction() output.

    Args:
        operation: Operation dict from adapter translation
        expected_topic: Expected Kafka topic
        expected_event_model: Expected event model class name
        expected_request_id: Expected request ID

    Raises:
        AssertionError: If any field doesn't match expectations

    Example:
        >>> operation = {
        ...     "topic": "archive.requests",
        ...     "event_model": "ArchiveRequestEvent",
        ...     "request_id": "req-123"
        ... }
        >>> assert_kafka_operation(
        ...     operation,
        ...     expected_topic="archive.requests",
        ...     expected_event_model="ArchiveRequestEvent",
        ...     expected_request_id="req-123"
        ... )
    """
    assert "topic" in operation, "Operation missing 'topic' field"
    assert "event_model" in operation, "Operation missing 'event_model' field"
    assert "request_id" in operation or "key" in operation, \
        "Operation missing 'request_id' or 'key' field"

    actual_topic = operation.get("topic")
    actual_event_model = operation.get("event_model")
    actual_request_id = operation.get("request_id") or operation.get("key")

    assert actual_topic == expected_topic, \
        f"Topic mismatch: expected '{expected_topic}', got '{actual_topic}'"

    assert actual_event_model == expected_event_model, \
        f"Event model mismatch: expected '{expected_event_model}', got '{actual_event_model}'"

    assert actual_request_id == expected_request_id, \
        f"Request ID mismatch: expected '{expected_request_id}', got '{actual_request_id}'"


def create_mock_kafka_config() -> Any:
    """
    Create mock Kafka configuration for Kafka adapter testing.

    Returns a mock config object with component_mappings for testing
    the KafkaTransportAdapter (Task 12 format).

    Returns:
        Mock KafkaConfig object with component_mappings attribute

    Example:
        >>> config = create_mock_kafka_config()
        >>> assert hasattr(config, 'component_mappings')
        >>> assert "archive_generator" in config.component_mappings
    """
    from unittest.mock import MagicMock

    # Mock archive_generator mapping
    archive_mapping = MagicMock()
    archive_mapping.request_topic = "archive.requests"
    archive_mapping.response_topics = {
        "success": "archive.completed",
        "failure": "archive.failed"
    }
    archive_mapping.event_models = {
        "request": "ArchiveRequestEvent",
        "success": "ArchiveCompletedEvent",
        "failure": "ArchiveFailedEvent"
    }

    # Mock metadata_extractor mapping
    metadata_mapping = MagicMock()
    metadata_mapping.request_topic = "metadata.requests"
    metadata_mapping.response_topics = {
        "success": "metadata.completed",
        "failure": "metadata.failed"
    }
    metadata_mapping.event_models = {
        "request": "MetadataExtractionRequestEvent",
        "success": "MetadataExtractionCompletedEvent",
        "failure": "MetadataExtractionFailedEvent"
    }

    # Mock Kafka config with component_mappings
    kafka_config = MagicMock()
    kafka_config.component_mappings = {
        "archive_generator": archive_mapping,
        "metadata_extractor": metadata_mapping
    }

    return kafka_config


# Deprecated: Use create_mock_kafka_config() instead (Task 12 update)
def create_mock_workflow_config() -> Any:
    """
    DEPRECATED: Use create_mock_kafka_config() instead.

    This function returns a mock Kafka config (not workflow config)
    for backward compatibility with tests written before Task 12.
    """
    return create_mock_kafka_config()
