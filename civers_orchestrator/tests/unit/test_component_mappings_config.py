"""Tests for component mapping configuration.

Following TDD: Write these tests FIRST (RED), then implement config changes (GREEN).

Component mappings are Kafka-specific configurations that map component identifiers
to Kafka topics and event model names. This keeps transport concerns separate from
workflow definitions.
"""

import pytest
from pydantic import ValidationError


class TestKafkaComponentMappingModel:
    """Test KafkaComponentMapping Pydantic model."""

    def test_valid_component_mapping(self):
        """Test creating valid component mapping."""
        from configs.models import KafkaComponentMapping

        mapping = KafkaComponentMapping(
            step_name="archive_generation",
            request_topic="archive.requests",
            response_topics={
                "success": "archive.completed",
                "failure": "archive.failed"
            },
            event_models={
                "request": "ArchiveRequestEvent",
                "success": "ArchiveCompletedEvent",
                "failure": "ArchiveFailedEvent"
            }
        )

        assert mapping.request_topic == "archive.requests"
        assert mapping.response_topics["success"] == "archive.completed"
        assert mapping.event_models["request"] == "ArchiveRequestEvent"

    def test_component_mapping_requires_request_topic(self):
        """Test that request_topic is required."""
        from configs.models import KafkaComponentMapping

        with pytest.raises(ValidationError, match="request_topic"):
            KafkaComponentMapping(
                response_topics={"success": "x", "failure": "y"},
                event_models={"request": "X", "success": "Y", "failure": "Z"}
            )

    def test_component_mapping_requires_response_topics(self):
        """Test that response_topics are required."""
        from configs.models import KafkaComponentMapping

        with pytest.raises(ValidationError, match="response_topics"):
            KafkaComponentMapping(
                request_topic="archive.requests",
                event_models={"request": "X", "success": "Y", "failure": "Z"}
            )

    def test_component_mapping_requires_event_models(self):
        """Test that event_models are required."""
        from configs.models import KafkaComponentMapping

        with pytest.raises(ValidationError, match="event_models"):
            KafkaComponentMapping(
                request_topic="archive.requests",
                response_topics={"success": "x", "failure": "y"}
            )

    def test_component_mapping_response_topics_must_have_success_failure(self):
        """Test that response_topics must include success and failure keys."""
        from configs.models import KafkaComponentMapping

        # This should validate that success/failure keys exist
        mapping = KafkaComponentMapping(
            step_name="archive_generation",
            request_topic="archive.requests",
            response_topics={
                "success": "archive.completed",
                "failure": "archive.failed"
            },
            event_models={
                "request": "ArchiveRequestEvent",
                "success": "ArchiveCompletedEvent",
                "failure": "ArchiveFailedEvent"
            }
        )

        assert "success" in mapping.response_topics
        assert "failure" in mapping.response_topics

    def test_component_mapping_event_models_must_have_required_keys(self):
        """Test that event_models must include request, success, failure keys."""
        from configs.models import KafkaComponentMapping

        mapping = KafkaComponentMapping(
            step_name="archive_generation",
            request_topic="archive.requests",
            response_topics={"success": "x", "failure": "y"},
            event_models={
                "request": "ArchiveRequestEvent",
                "success": "ArchiveCompletedEvent",
                "failure": "ArchiveFailedEvent"
            }
        )

        assert "request" in mapping.event_models
        assert "success" in mapping.event_models
        assert "failure" in mapping.event_models


class TestKafkaConfigWithComponentMappings:
    """Test KafkaConfig model with component_mappings field."""

    def test_kafka_config_with_component_mappings(self):
        """Test KafkaConfig accepts component_mappings."""
        from configs.models import KafkaConfig

        config_dict = {
            "bootstrap_servers": "localhost:29092",
            "consumer": {
                "group_id": "test-group",
                "auto_offset_reset": "earliest"
            },
            "producer": {
                "acks": "all",
                "retries": 3
            },
            "topics": {
                "orchestrator_requests": "orchestrator.requests",
                "orchestrator_status": "orchestrator.status",
                "orchestrator_completed": "orchestrator.completed",
                "orchestrator_failed": "orchestrator.failed"
            },
            "component_mappings": {
                "archive_generator": {
                    "step_name": "archive_generation",
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
                }
            }
        }

        config = KafkaConfig(**config_dict)

        assert "archive_generator" in config.component_mappings
        assert config.component_mappings["archive_generator"].request_topic == "archive.requests"

    def test_kafka_config_component_mappings_optional(self):
        """Test that component_mappings is optional for backward compatibility."""
        from configs.models import KafkaConfig

        config_dict = {
            "bootstrap_servers": "localhost:29092",
            "consumer": {
                "group_id": "test-group",
                "auto_offset_reset": "earliest"
            },
            "producer": {
                "acks": "all",
                "retries": 3
            },
            "topics": {
                "orchestrator_requests": "orchestrator.requests",
                "orchestrator_status": "orchestrator.status",
                "orchestrator_completed": "orchestrator.completed",
                "orchestrator_failed": "orchestrator.failed"
            }
        }

        config = KafkaConfig(**config_dict)

        # Should have empty dict as default
        assert hasattr(config, 'component_mappings')
        assert config.component_mappings == {}

    def test_kafka_config_multiple_component_mappings(self):
        """Test KafkaConfig with multiple component mappings."""
        from configs.models import KafkaConfig

        config_dict = {
            "bootstrap_servers": "localhost:29092",
            "consumer": {"group_id": "test", "auto_offset_reset": "earliest"},
            "producer": {"acks": "all", "retries": 3},
            "topics": {
                "orchestrator_requests": "orchestrator.requests",
                "orchestrator_status": "orchestrator.status",
                "orchestrator_completed": "orchestrator.completed",
                "orchestrator_failed": "orchestrator.failed"
            },
            "component_mappings": {
                "archive_generator": {
                    "step_name": "archive_generation",
                    "request_topic": "archive.requests",
                    "response_topics": {"success": "archive.completed", "failure": "archive.failed"},
                    "event_models": {"request": "ArchiveRequestEvent", "success": "ArchiveCompletedEvent", "failure": "ArchiveFailedEvent"}
                },
                "metadata_extractor": {
                    "step_name": "metadata_extraction",
                    "request_topic": "metadata.requests",
                    "response_topics": {"success": "metadata.completed", "failure": "metadata.failed"},
                    "event_models": {"request": "MetadataExtractionRequestEvent", "success": "MetadataExtractionCompletedEvent", "failure": "MetadataExtractionFailedEvent"}
                }
            }
        }

        config = KafkaConfig(**config_dict)

        assert len(config.component_mappings) == 2
        assert "archive_generator" in config.component_mappings
        assert "metadata_extractor" in config.component_mappings


class TestComponentMappingsConfigLoading:
    """Test loading component mappings from kafka.yaml."""

    def test_load_config_with_component_mappings(self):
        """Test that config loader loads component_mappings from kafka.yaml."""
        from configs.loaders import YamlFileConfigLoader

        config = YamlFileConfigLoader().load()

        # Should have loaded component mappings from kafka.yaml
        assert hasattr(config.transport.kafka, 'component_mappings')
        assert isinstance(config.transport.kafka.component_mappings, dict)

    def test_component_mappings_includes_archive_generator(self):
        """Test that component_mappings includes archive_generator."""
        from configs.loaders import YamlFileConfigLoader

        config = YamlFileConfigLoader().load()

        assert "archive_generator" in config.transport.kafka.component_mappings
        mapping = config.transport.kafka.component_mappings["archive_generator"]
        assert mapping.request_topic == "test.archive.requests"
        assert mapping.response_topics["success"] == "test.archive.completed"
        assert mapping.event_models["request"] == "ArchiveRequestEvent"

    def test_component_mappings_includes_metadata_extractor(self):
        """Test that component_mappings includes metadata_extractor."""
        from configs.loaders import YamlFileConfigLoader

        config = YamlFileConfigLoader().load()

        assert "metadata_extractor" in config.transport.kafka.component_mappings
        mapping = config.transport.kafka.component_mappings["metadata_extractor"]
        assert mapping.request_topic == "test.metadata.requests"

    def test_component_mappings_includes_doi_service(self):
        """Test that component_mappings includes doi_service."""
        from configs.loaders import YamlFileConfigLoader

        config = YamlFileConfigLoader().load()

        assert "doi_service" in config.transport.kafka.component_mappings
        mapping = config.transport.kafka.component_mappings["doi_service"]
        assert mapping.request_topic == "test.doi.requests"




class TestKafkaAdapterWithComponentMappings:
    """Test KafkaTransportAdapter loads from component_mappings config."""

    def test_adapter_initializes_with_config_component_mappings(self):
        """Test adapter loads component mappings from config."""
        from configs.loaders import YamlFileConfigLoader
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter

        config = YamlFileConfigLoader().load()
        adapter = KafkaTransportAdapter(config.transport.kafka)

        assert len(adapter.component_mappings) > 0
        assert "archive_generator" in adapter.component_mappings

    def test_adapter_uses_config_mappings_not_workflow_extraction(self):
        """Test adapter uses config mappings directly, not workflow extraction."""
        from configs.loaders import YamlFileConfigLoader
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter

        config = YamlFileConfigLoader().load()
        adapter = KafkaTransportAdapter(config.transport.kafka)

        # Should work even if we pass config without workflows attribute
        # (proving it's not extracting from workflows)
        mapping = adapter.component_mappings["archive_generator"]
        assert mapping["request_topic"] == "test.archive.requests"
        assert mapping["event_models"]["request"] == "ArchiveRequestEvent"

    def test_adapter_get_request_destination_uses_config_mappings(self):
        """Test adapter methods use config-based mappings."""
        from configs.loaders import YamlFileConfigLoader
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter

        config = YamlFileConfigLoader().load()
        adapter = KafkaTransportAdapter(config.transport.kafka)

        topic = adapter.get_request_destination("archive_generator")

        assert topic == "test.archive.requests"

    def test_adapter_all_components_accessible(self):
        """Test adapter can access all configured components."""
        from configs.loaders import YamlFileConfigLoader
        from transport_services.adapters.kafka_adapter import KafkaTransportAdapter

        config = YamlFileConfigLoader().load()
        adapter = KafkaTransportAdapter(config.transport.kafka)

        # All 3 components should be accessible
        assert adapter.get_request_destination("archive_generator") == "test.archive.requests"
        assert adapter.get_request_destination("metadata_extractor") == "test.metadata.requests"
        assert adapter.get_request_destination("doi_service") == "test.doi.requests"
