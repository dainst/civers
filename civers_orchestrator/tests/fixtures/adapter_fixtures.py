"""Pytest fixtures for adapter testing.

These fixtures provide pre-configured test data for testing
transport adapters and the refactored architecture.

Usage:
    # In conftest.py or test file
    from tests.fixtures.adapter_fixtures import *

    # In tests
    def test_something(kafka_component_mappings):
        assert "archive_generator" in kafka_component_mappings
"""

import pytest
from typing import Dict, Any


@pytest.fixture
def kafka_component_mappings() -> Dict[str, Dict[str, Any]]:
    """
    Component mappings for Kafka adapter tests.

    Mirrors structure from kafka.yaml component_mappings section
    (will be added in Task 12).

    Returns:
        Dict mapping component IDs to Kafka topics/events

    Example:
        >>> def test_adapter(kafka_component_mappings):
        ...     mapping = kafka_component_mappings["archive_generator"]
        ...     assert mapping["request_topic"] == "archive.requests"
    """
    return {
        "archive_generator": {
            "request_topic": "archive.requests",
            "response_topics": {
                "success": "archive.completed",
                "failure": "archive.failed"
            },
            "event_models": {
                "request": "ArchiveRequestEvent",
                "success": "ArchiveCompletedEvent",
                "failure": "ArchiveFailedEvent"
            }
        },
        "metadata_extractor": {
            "request_topic": "metadata.requests",
            "response_topics": {
                "success": "metadata.completed",
                "failure": "metadata.failed"
            },
            "event_models": {
                "request": "MetadataExtractionRequestEvent",
                "success": "MetadataExtractionCompletedEvent",
                "failure": "MetadataExtractionFailedEvent"
            }
        },
        "doi_service": {
            "request_topic": "doi.requests",
            "response_topics": {
                "success": "doi.completed",
                "failure": "doi.failed"
            },
            "event_models": {
                "request": "DOIRequestEvent",
                "success": "DOICompletedEvent",
                "failure": "DOIFailedEvent"
            }
        }
    }


@pytest.fixture
def mock_transport_adapter():
    """
    Fixture providing configured mock adapter.

    Returns pre-configured MockTransportAdapter with common component
    mappings already set up.

    Returns:
        MockTransportAdapter instance

    Example:
        >>> def test_orchestrator(mock_transport_adapter):
        ...     # Use in tests without manual configuration
        ...     result = mock_transport_adapter.get_request_destination("archive_generator")
        ...     assert result == "archive.requests"
    """
    from tests.mocks.mock_transport_adapter import MockTransportAdapter

    adapter = MockTransportAdapter()

    # Pre-configure common component mappings
    adapter.set_mock_mapping("archive_generator", {
        "request_destination": "archive.requests",
        "response_destinations": {
            "success": "archive.completed",
            "failure": "archive.failed"
        },
        "request_message_type": "ArchiveRequestEvent"
    })

    adapter.set_mock_mapping("metadata_extractor", {
        "request_destination": "metadata.requests",
        "response_destinations": {
            "success": "metadata.completed",
            "failure": "metadata.failed"
        },
        "request_message_type": "MetadataExtractionRequestEvent"
    })

    adapter.set_mock_mapping("doi_service", {
        "request_destination": "doi.requests",
        "response_destinations": {
            "success": "doi.completed",
            "failure": "doi.failed"
        },
        "request_message_type": "DOIRequestEvent"
    })

    return adapter
