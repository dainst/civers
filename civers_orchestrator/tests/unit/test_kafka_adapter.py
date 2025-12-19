"""Tests for Kafka transport adapter.

Following TDD: Write these tests FIRST (RED), then implement adapter (GREEN).

The Kafka adapter translates transport-agnostic component identifiers
into Kafka-specific topics and event model names by reading component
mappings from workflow configurations.
"""

import pytest
from typing import Dict, Any


class TestKafkaAdapterInitialization:
    """Test Kafka adapter initialization and configuration loading."""

    def test_kafka_adapter_initializes_with_workflow_config(self):
        """Test adapter initializes and loads component mappings from workflows."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        assert adapter is not None
        assert hasattr(adapter, 'component_mappings')

    def test_kafka_adapter_extracts_archive_generator_mapping(self):
        """Test adapter extracts archive generator component mapping."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        # Should extract mapping from workflow steps
        assert "archive_generator" in adapter.component_mappings
        mapping = adapter.component_mappings["archive_generator"]
        assert "request_topic" in mapping
        assert "response_topics" in mapping
        assert "event_models" in mapping

    def test_kafka_adapter_extracts_metadata_extractor_mapping(self):
        """Test adapter extracts metadata extractor component mapping."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        assert "metadata_extractor" in adapter.component_mappings
        mapping = adapter.component_mappings["metadata_extractor"]
        assert mapping["request_topic"] == "metadata.requests"
        assert mapping["response_topics"]["success"] == "metadata.completed"


class TestKafkaAdapterRequestDestination:
    """Test getting Kafka request topics for components."""

    def test_get_request_destination_for_archive_generator(self, kafka_component_mappings):
        """Test adapter returns correct Kafka topic for archive generator requests."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        result = adapter.get_request_destination("archive_generator")

        assert result == "archive.requests"

    def test_get_request_destination_for_metadata_extractor(self):
        """Test adapter returns correct Kafka topic for metadata extractor."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        result = adapter.get_request_destination("metadata_extractor")

        assert result == "metadata.requests"

    def test_get_request_destination_raises_for_unmapped_component(self):
        """Test adapter raises error for component without mapping."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        with pytest.raises(ValueError, match="No mapping found for component"):
            adapter.get_request_destination("unknown_component")


class TestKafkaAdapterResponseDestinations:
    """Test getting Kafka response topics for components."""

    def test_get_response_destinations_for_archive_generator(self):
        """Test adapter returns success/failure topics for archive generator."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        result = adapter.get_response_destinations("archive_generator")

        assert result["success"] == "archive.completed"
        assert result["failure"] == "archive.failed"

    def test_get_response_destinations_for_metadata_extractor(self):
        """Test adapter returns success/failure topics for metadata extractor."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        result = adapter.get_response_destinations("metadata_extractor")

        assert result["success"] == "metadata.completed"
        assert result["failure"] == "metadata.failed"

    def test_get_response_destinations_raises_for_unmapped_component(self):
        """Test adapter raises error for component without mapping."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        with pytest.raises(ValueError, match="No mapping found for component"):
            adapter.get_response_destinations("unknown_component")


class TestKafkaAdapterMessageTypes:
    """Test getting event model names for components."""

    def test_get_message_type_for_archive_request(self):
        """Test adapter returns correct event model for archive request."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        result = adapter.get_message_type("archive_generator", "request")

        assert result == "ArchiveRequestEvent"

    def test_get_message_type_for_archive_success(self):
        """Test adapter returns correct event model for archive success."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        result = adapter.get_message_type("archive_generator", "success")

        assert result == "ArchiveCompletedEvent"

    def test_get_message_type_for_archive_failure(self):
        """Test adapter returns correct event model for archive failure."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        result = adapter.get_message_type("archive_generator", "failure")

        assert result == "ArchiveFailedEvent"

    def test_get_message_type_for_metadata_request(self):
        """Test adapter returns correct event model for metadata request."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        result = adapter.get_message_type("metadata_extractor", "request")

        assert result == "MetadataExtractionRequestEvent"

    def test_get_message_type_raises_for_invalid_outcome(self):
        """Test adapter raises error for invalid outcome."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        with pytest.raises(ValueError, match="Invalid outcome"):
            adapter.get_message_type("archive_generator", "invalid_outcome")

    def test_get_message_type_raises_for_unmapped_component(self):
        """Test adapter raises error for unmapped component."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        with pytest.raises(ValueError, match="No mapping found for component"):
            adapter.get_message_type("unknown_component", "request")


class TestKafkaAdapterTranslation:
    """Test translating transport-agnostic instructions to Kafka operations."""

    def test_translate_instruction_for_archive_generator(self):
        """Test adapter translates archive generator instruction correctly."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import (
            create_mock_workflow_config,
            create_transport_agnostic_instruction
        )

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        instruction = create_transport_agnostic_instruction(
            component="archive_generator",
            request_id="req-123",
            input_data={"url": "https://example.com"}
        )

        result = adapter.translate_instruction(instruction)

        assert result["topic"] == "archive.requests"
        assert result["event_model"] == "ArchiveRequestEvent"
        assert result["event_data"]["url"] == "https://example.com"
        assert result["event_data"]["request_id"] == "req-123"

    def test_translate_instruction_for_metadata_extractor(self):
        """Test adapter translates metadata extractor instruction correctly."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import (
            create_mock_workflow_config,
            create_transport_agnostic_instruction
        )

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        instruction = create_transport_agnostic_instruction(
            component="metadata_extractor",
            request_id="req-456",
            input_data={"archive_path": "/path/to/archive.warc"}
        )

        result = adapter.translate_instruction(instruction)

        assert result["topic"] == "metadata.requests"
        assert result["event_model"] == "MetadataExtractionRequestEvent"
        assert result["event_data"]["archive_path"] == "/path/to/archive.warc"
        assert result["event_data"]["request_id"] == "req-456"

    def test_translate_instruction_includes_key_from_request_id(self):
        """Test translation includes Kafka key derived from request_id."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import (
            create_mock_workflow_config,
            create_transport_agnostic_instruction
        )

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        instruction = create_transport_agnostic_instruction(
            component="archive_generator",
            request_id="req-789"
        )

        result = adapter.translate_instruction(instruction)

        assert "key" in result
        assert result["key"] == "req-789"

    def test_translate_instruction_preserves_metadata(self):
        """Test translation preserves instruction metadata."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import (
            create_mock_workflow_config,
            create_transport_agnostic_instruction
        )

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        instruction = create_transport_agnostic_instruction(
            component="archive_generator",
            metadata={"callback_url": "https://callback.example.com"}
        )

        result = adapter.translate_instruction(instruction)

        assert "metadata" in result
        assert result["metadata"]["callback_url"] == "https://callback.example.com"

    def test_translate_instruction_raises_for_unmapped_component(self):
        """Test translation raises error for unmapped component."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import (
            create_mock_workflow_config,
            create_transport_agnostic_instruction
        )

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        instruction = create_transport_agnostic_instruction(
            component="unknown_component"
        )

        with pytest.raises(ValueError, match="No mapping found for component"):
            adapter.translate_instruction(instruction)


class TestKafkaAdapterComplianceWithInterface:
    """Test Kafka adapter implements TransportAdapter interface correctly."""

    def test_kafka_adapter_implements_transport_adapter_interface(self):
        """Test Kafka adapter is instance of TransportAdapter."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from transport_services.adapters.transport_adapter_interface import TransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        assert isinstance(adapter, TransportAdapter)

    def test_kafka_adapter_has_all_required_methods(self):
        """Test Kafka adapter implements all abstract methods."""
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter
        from tests.utils.test_helpers import create_mock_workflow_config

        workflow_config = create_mock_workflow_config()
        adapter = KafkaTransportAdapter(workflow_config)

        assert hasattr(adapter, 'get_request_destination')
        assert callable(adapter.get_request_destination)
        assert hasattr(adapter, 'get_response_destinations')
        assert callable(adapter.get_response_destinations)
        assert hasattr(adapter, 'translate_instruction')
        assert callable(adapter.translate_instruction)
        assert hasattr(adapter, 'get_message_type')
        assert callable(adapter.get_message_type)
