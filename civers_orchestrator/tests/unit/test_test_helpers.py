"""Tests for test helper utilities (meta-testing).

Following TDD: These tests are written FIRST to define expected behavior
of test utilities that will be used in Tasks 11-15.
"""

import pytest


class TestCreateTransportAgnosticInstruction:
    """Test helper for creating transport-agnostic instructions."""

    def test_creates_instruction_with_defaults(self):
        """Test helper creates instruction with default values."""
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        instruction = create_transport_agnostic_instruction()

        assert instruction.request_id == "test-001"
        assert instruction.url == "https://example.com"
        assert instruction.component == "test_component"
        assert instruction.input_schema == "TestRequest"
        assert isinstance(instruction.input_data, dict)

    def test_creates_instruction_with_custom_values(self):
        """Test helper accepts custom values."""
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        instruction = create_transport_agnostic_instruction(
            request_id="custom-123",
            url="https://custom.com",
            component="custom_component",
            input_schema="CustomSchema",
            input_data={"key": "value"}
        )

        assert instruction.request_id == "custom-123"
        assert instruction.url == "https://custom.com"
        assert instruction.component == "custom_component"
        assert instruction.input_schema == "CustomSchema"
        assert instruction.input_data == {"key": "value"}

    def test_instruction_has_no_transport_specific_fields(self):
        """Test instruction doesn't have Kafka-specific fields."""
        from tests.utils.test_helpers import create_transport_agnostic_instruction

        instruction = create_transport_agnostic_instruction()

        # Should NOT have these old Kafka-specific fields
        assert not hasattr(instruction, "input_topic")
        assert not hasattr(instruction, "input_event_model")

        # Should HAVE these transport-agnostic fields
        assert hasattr(instruction, "component")
        assert hasattr(instruction, "input_schema")
        assert hasattr(instruction, "input_data")


class TestCreateMockComponentMapping:
    """Test helper for creating component mappings."""

    def test_creates_valid_kafka_mapping_structure(self):
        """Test helper creates valid Kafka component mapping."""
        from tests.utils.test_helpers import create_mock_component_mapping

        mapping = create_mock_component_mapping(
            component="test_component",
            request_topic="test.requests",
            success_topic="test.success",
            failure_topic="test.failure",
            request_event="TestRequestEvent",
            success_event="TestSuccessEvent",
            failure_event="TestFailureEvent"
        )

        # Verify structure matches Kafka adapter expectations
        assert mapping["request_topic"] == "test.requests"
        assert mapping["response_topics"]["success"] == "test.success"
        assert mapping["response_topics"]["failure"] == "test.failure"
        assert mapping["event_models"]["request"] == "TestRequestEvent"
        assert mapping["event_models"]["success"] == "TestSuccessEvent"
        assert mapping["event_models"]["failure"] == "TestFailureEvent"

    def test_mapping_has_required_keys(self):
        """Test mapping contains all required keys."""
        from tests.utils.test_helpers import create_mock_component_mapping

        mapping = create_mock_component_mapping(
            component="test",
            request_topic="t1",
            success_topic="t2",
            failure_topic="t3",
            request_event="E1",
            success_event="E2",
            failure_event="E3"
        )

        assert "request_topic" in mapping
        assert "response_topics" in mapping
        assert "event_models" in mapping
        assert "success" in mapping["response_topics"]
        assert "failure" in mapping["response_topics"]


class TestAssertKafkaOperation:
    """Test assertion helper for Kafka operations."""

    def test_assertion_passes_for_matching_operation(self):
        """Test assertion passes when operation matches expectations."""
        from tests.utils.test_helpers import assert_kafka_operation

        operation = {
            "topic": "test.topic",
            "event_model": "TestEvent",
            "request_id": "test-123"
        }

        # Should not raise
        assert_kafka_operation(
            operation,
            expected_topic="test.topic",
            expected_event_model="TestEvent",
            expected_request_id="test-123"
        )

    def test_assertion_fails_for_wrong_topic(self):
        """Test assertion fails when topic doesn't match."""
        from tests.utils.test_helpers import assert_kafka_operation

        operation = {
            "topic": "test.topic",
            "event_model": "TestEvent",
            "request_id": "test-123"
        }

        with pytest.raises(AssertionError, match="topic"):
            assert_kafka_operation(
                operation,
                expected_topic="wrong.topic",
                expected_event_model="TestEvent",
                expected_request_id="test-123"
            )

    def test_assertion_fails_for_wrong_event_model(self):
        """Test assertion fails when event model doesn't match."""
        from tests.utils.test_helpers import assert_kafka_operation

        operation = {
            "topic": "test.topic",
            "event_model": "TestEvent",
            "request_id": "test-123"
        }

        with pytest.raises(AssertionError, match="Event model mismatch"):
            assert_kafka_operation(
                operation,
                expected_topic="test.topic",
                expected_event_model="WrongEvent",
                expected_request_id="test-123"
            )

    def test_assertion_fails_for_wrong_request_id(self):
        """Test assertion fails when request_id doesn't match."""
        from tests.utils.test_helpers import assert_kafka_operation

        operation = {
            "topic": "test.topic",
            "event_model": "TestEvent",
            "request_id": "test-123"
        }

        with pytest.raises(AssertionError, match="Request ID mismatch"):
            assert_kafka_operation(
                operation,
                expected_topic="test.topic",
                expected_event_model="TestEvent",
                expected_request_id="wrong-id"
            )
