"""Tests for pytest fixtures.

Following TDD: These tests verify fixtures provide correct test data.
"""



class TestKafkaComponentMappingsFixture:
    """Test Kafka component mappings fixture."""

    def test_fixture_provides_component_mappings(self, kafka_component_mappings):
        """Test fixture provides valid component mappings structure."""
        assert isinstance(kafka_component_mappings, dict)
        assert len(kafka_component_mappings) > 0

    def test_fixture_includes_archive_generator(self, kafka_component_mappings):
        """Test fixture includes archive generator mapping."""
        assert "archive_generator" in kafka_component_mappings

        mapping = kafka_component_mappings["archive_generator"]
        assert "request_topic" in mapping
        assert "response_topics" in mapping
        assert "event_models" in mapping

    def test_fixture_includes_metadata_extractor(self, kafka_component_mappings):
        """Test fixture includes metadata extractor mapping."""
        assert "metadata_extractor" in kafka_component_mappings

        mapping = kafka_component_mappings["metadata_extractor"]
        assert mapping["request_topic"] == "metadata.requests"
        assert mapping["response_topics"]["success"] == "metadata.completed"

    def test_fixture_mapping_has_correct_structure(self, kafka_component_mappings):
        """Test each mapping has required fields."""
        for component, mapping in kafka_component_mappings.items():
            assert "request_topic" in mapping
            assert "response_topics" in mapping
            assert "success" in mapping["response_topics"]
            assert "failure" in mapping["response_topics"]
            assert "event_models" in mapping
            assert "request" in mapping["event_models"]
            assert "success" in mapping["event_models"]
            assert "failure" in mapping["event_models"]


class TestMockTransportAdapterFixture:
    """Test mock transport adapter fixture."""

    def test_fixture_provides_configured_adapter(self, mock_transport_adapter):
        """Test fixture provides pre-configured mock adapter."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter

        assert isinstance(mock_transport_adapter, MockTransportAdapter)

    def test_fixture_adapter_has_archive_generator_mapping(self, mock_transport_adapter):
        """Test fixture adapter is pre-configured with archive generator."""
        result = mock_transport_adapter.get_request_destination("archive_generator")

        assert result == "archive.requests"

    def test_fixture_adapter_can_translate(self, mock_transport_adapter):
        """Test fixture adapter can translate instructions."""
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        instruction = create_transport_agnostic_instruction(
            component="archive_generator"
        )
        result = mock_transport_adapter.translate_instruction(instruction)

        assert "destination" in result
        assert result["destination"] == "archive.requests"
