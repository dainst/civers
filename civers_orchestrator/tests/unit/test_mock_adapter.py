"""Tests for mock transport adapter.

Following TDD: These tests define expected behavior of the mock adapter
that will be used in orchestrator tests (Tasks 13-14).
"""



class TestMockTransportAdapterBasics:
    """Test basic mock adapter functionality."""

    def test_mock_adapter_initializes(self):
        """Test mock adapter can be instantiated."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter

        adapter = MockTransportAdapter()

        assert adapter is not None
        assert hasattr(adapter, 'translation_calls')
        assert hasattr(adapter, 'mock_mappings')

    def test_mock_adapter_starts_with_empty_calls(self):
        """Test adapter initializes with no recorded calls."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter

        adapter = MockTransportAdapter()

        assert len(adapter.translation_calls) == 0
        assert len(adapter.mock_mappings) == 0


class TestMockAdapterConfiguration:
    """Test configuring mock adapter with mappings."""

    def test_set_mock_mapping(self):
        """Test setting mock mapping for a component."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter

        adapter = MockTransportAdapter()
        adapter.set_mock_mapping("test_component", {
            "request_destination": "test.destination",
            "response_destinations": {
                "success": "test.success",
                "failure": "test.failure"
            }
        })

        assert "test_component" in adapter.mock_mappings
        assert adapter.mock_mappings["test_component"]["request_destination"] == "test.destination"

    def test_get_request_destination_returns_configured_value(self):
        """Test adapter returns configured request destination."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter

        adapter = MockTransportAdapter()
        adapter.set_mock_mapping("archive_generator", {
            "request_destination": "archive.requests"
        })

        result = adapter.get_request_destination("archive_generator")

        assert result == "archive.requests"

    def test_get_response_destinations_returns_configured_values(self):
        """Test adapter returns configured response destinations."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter

        adapter = MockTransportAdapter()
        adapter.set_mock_mapping("archive_generator", {
            "response_destinations": {
                "success": "archive.completed",
                "failure": "archive.failed"
            }
        })

        result = adapter.get_response_destinations("archive_generator")

        assert result["success"] == "archive.completed"
        assert result["failure"] == "archive.failed"


class TestMockAdapterTranslation:
    """Test mock adapter translates instructions."""

    def test_translate_instruction_records_call(self):
        """Test adapter records translation calls for verification."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        adapter = MockTransportAdapter()
        adapter.set_mock_mapping("test_component", {
            "request_destination": "test.dest"
        })

        instruction = create_transport_agnostic_instruction(component="test_component")
        adapter.translate_instruction(instruction)

        assert len(adapter.translation_calls) == 1
        assert adapter.translation_calls[0] == instruction

    def test_translate_instruction_returns_mock_operation(self):
        """Test adapter returns mock operation dict."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        adapter = MockTransportAdapter()
        adapter.set_mock_mapping("test_component", {
            "request_destination": "custom.destination",
            "request_message_type": "CustomMessage"
        })

        instruction = create_transport_agnostic_instruction(
            component="test_component",
            request_id="req-123"
        )
        result = adapter.translate_instruction(instruction)

        assert result["destination"] == "custom.destination"
        assert result["message_type"] == "CustomMessage"
        assert result["request_id"] == "req-123"

    def test_translate_instruction_includes_data(self):
        """Test translation includes instruction data."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        adapter = MockTransportAdapter()
        adapter.set_mock_mapping("test_component", {})

        instruction = create_transport_agnostic_instruction(
            component="test_component",
            input_data={"key": "value"}
        )
        result = adapter.translate_instruction(instruction)

        assert result["data"] == {"key": "value"}

    def test_multiple_calls_recorded(self):
        """Test adapter records multiple translation calls."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        adapter = MockTransportAdapter()
        adapter.set_mock_mapping("comp1", {})
        adapter.set_mock_mapping("comp2", {})

        inst1 = create_transport_agnostic_instruction(component="comp1")
        inst2 = create_transport_agnostic_instruction(component="comp2")

        adapter.translate_instruction(inst1)
        adapter.translate_instruction(inst2)

        assert len(adapter.translation_calls) == 2
        assert adapter.translation_calls[0] == inst1
        assert adapter.translation_calls[1] == inst2


class TestMockAdapterVerification:
    """Test using mock adapter for verification in tests."""

    def test_can_verify_orchestrator_called_adapter(self):
        """Test mock can verify orchestrator called adapter correctly."""
        from tests.mocks.mock_transport_adapter import MockTransportAdapter
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        adapter = MockTransportAdapter()
        adapter.set_mock_mapping("archive_generator", {
            "request_destination": "archive.requests"
        })

        # Simulate orchestrator calling adapter
        instruction = create_transport_agnostic_instruction(
            component="archive_generator",
            request_id="req-001"
        )
        adapter.translate_instruction(instruction)

        # Verification assertions
        assert len(adapter.translation_calls) == 1
        assert adapter.translation_calls[0].component == "archive_generator"
        assert adapter.translation_calls[0].request_id == "req-001"
