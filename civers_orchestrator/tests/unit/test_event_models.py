"""Unit tests for event models."""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


class TestEventBaseModel:
    """Tests for EventBaseModel base class."""

    def test_valid_event_creation(self):
        """Test creating a valid base event with all required fields."""
        from transport_services.kafka.event_models import EventBaseModel

        event = EventBaseModel(
            request_id="req-123",
            url="https://example.com/page"
        )

        assert event.request_id == "req-123"
        assert event.url == "https://example.com/page"
        assert event.created_at is not None
        # Verify timestamp is ISO 8601 format
        datetime.fromisoformat(event.created_at)

    def test_invalid_request_id_empty(self):
        """Test that empty request_id raises ValidationError."""
        from transport_services.kafka.event_models import EventBaseModel

        with pytest.raises(ValidationError) as exc_info:
            EventBaseModel(
                request_id="",
                url="https://example.com/page"
            )

        assert "request_id" in str(exc_info.value)

    def test_invalid_request_id_whitespace(self):
        """Test that whitespace-only request_id raises ValidationError."""
        from transport_services.kafka.event_models import EventBaseModel

        with pytest.raises(ValidationError) as exc_info:
            EventBaseModel(
                request_id="   ",
                url="https://example.com/page"
            )

        assert "request_id" in str(exc_info.value)

    def test_invalid_url_empty(self):
        """Test that empty URL raises ValidationError."""
        from transport_services.kafka.event_models import EventBaseModel

        with pytest.raises(ValidationError) as exc_info:
            EventBaseModel(
                request_id="req-123",
                url=""
            )

        assert "url" in str(exc_info.value)

    def test_invalid_url_format(self):
        """Test that whitespace-only URL raises ValidationError.

        Note: Following CiVers pattern - we only validate non-empty,
        not full URL format validation.
        """
        from transport_services.kafka.event_models import EventBaseModel

        with pytest.raises(ValidationError) as exc_info:
            EventBaseModel(
                request_id="req-123",
                url="   "
            )

        assert "url" in str(exc_info.value)

    def test_timestamp_auto_generated(self):
        """Test that created_at timestamp is auto-generated in ISO 8601 UTC format."""
        from transport_services.kafka.event_models import EventBaseModel

        before = datetime.now(timezone.utc).replace(microsecond=0)
        event = EventBaseModel(
            request_id="req-123",
            url="https://example.com/page"
        )
        after = datetime.now(timezone.utc).replace(microsecond=0)

        # Parse the timestamp (replace Z with +00:00 for parsing)
        timestamp = datetime.fromisoformat(event.created_at.replace('Z', '+00:00'))

        # Verify it's between before and after (within 1 second tolerance)
        assert before <= timestamp <= after or (timestamp - before).total_seconds() < 2

        # Verify it ends with 'Z' (CiVers pattern)
        assert event.created_at.endswith('Z')

    def test_custom_timestamp(self):
        """Test that custom created_at timestamp can be provided (Z suffix format)."""
        from transport_services.kafka.event_models import EventBaseModel

        custom_time = "2024-01-15T10:30:00Z"
        event = EventBaseModel(
            request_id="req-123",
            url="https://example.com/page",
            created_at=custom_time
        )

        assert event.created_at == custom_time

    def test_json_serialization(self):
        """Test that event can be serialized to JSON."""
        from transport_services.kafka.event_models import EventBaseModel

        event = EventBaseModel(
            request_id="req-123",
            url="https://example.com/page"
        )

        # Serialize to JSON
        json_str = event.model_dump_json()
        data = json.loads(json_str)

        assert data["request_id"] == "req-123"
        assert data["url"] == "https://example.com/page"
        assert "created_at" in data

    def test_json_deserialization(self):
        """Test that event can be deserialized from JSON (Z suffix format)."""
        from transport_services.kafka.event_models import EventBaseModel

        json_data = {
            "request_id": "req-456",
            "url": "https://example.com/other",
            "created_at": "2024-01-15T10:30:00Z"
        }

        event = EventBaseModel(**json_data)

        assert event.request_id == "req-456"
        assert event.url == "https://example.com/other"
        assert event.created_at == "2024-01-15T10:30:00Z"


class TestOrchestratorRequestEvent:
    """Tests for OrchestratorRequestEvent."""

    def test_valid_request_event(self):
        """Test creating a valid orchestrator request event."""
        from transport_services.kafka.event_models import OrchestratorRequestEvent

        event = OrchestratorRequestEvent(
            request_id="req-123",
            url="https://example.com/page"
        )

        assert event.request_id == "req-123"
        assert event.url == "https://example.com/page"
        assert event.workflow_name is None
        assert event.priority == 1  # default
        assert event.metadata == {}

    def test_request_event_with_optional_fields(self):
        """Test request event with all optional fields."""
        from transport_services.kafka.event_models import OrchestratorRequestEvent

        event = OrchestratorRequestEvent(
            request_id="req-123",
            url="https://example.com/page",
            workflow_name="archaeology_workflow",
            priority=5,
            callback_url="https://example.com/webhook",
            metadata={"source": "api", "user": "test"}
        )

        assert event.workflow_name == "archaeology_workflow"
        assert event.priority == 5
        assert event.callback_url == "https://example.com/webhook"
        assert event.metadata == {"source": "api", "user": "test"}

    def test_request_event_with_callback_url(self):
        """Test request event with callback URL."""
        from transport_services.kafka.event_models import OrchestratorRequestEvent

        event = OrchestratorRequestEvent(
            request_id="req-123",
            url="https://example.com/page",
            callback_url="https://external.system/webhooks/orchestrator"
        )

        assert event.callback_url == "https://external.system/webhooks/orchestrator"

    def test_request_event_without_callback_url(self):
        """Test that callback_url is optional and defaults to None."""
        from transport_services.kafka.event_models import OrchestratorRequestEvent

        event = OrchestratorRequestEvent(
            request_id="req-123",
            url="https://example.com/page"
        )

        assert event.callback_url is None

    def test_request_event_priority_validation_min(self):
        """Test that priority less than 1 raises ValidationError."""
        from transport_services.kafka.event_models import OrchestratorRequestEvent

        with pytest.raises(ValidationError) as exc_info:
            OrchestratorRequestEvent(
                request_id="req-123",
                url="https://example.com/page",
                priority=0
            )

        assert "priority" in str(exc_info.value)

    def test_request_event_priority_validation_max(self):
        """Test that priority greater than 10 raises ValidationError."""
        from transport_services.kafka.event_models import OrchestratorRequestEvent

        with pytest.raises(ValidationError) as exc_info:
            OrchestratorRequestEvent(
                request_id="req-123",
                url="https://example.com/page",
                priority=11
            )

        assert "priority" in str(exc_info.value)

    def test_request_event_json_serialization(self):
        """Test request event JSON serialization."""
        from transport_services.kafka.event_models import OrchestratorRequestEvent

        event = OrchestratorRequestEvent(
            request_id="req-123",
            url="https://example.com/page",
            priority=3
        )

        json_str = event.model_dump_json()
        data = json.loads(json_str)

        assert data["request_id"] == "req-123"
        assert data["priority"] == 3


class TestOrchestratorStatusEvent:
    """Tests for OrchestratorStatusEvent."""

    def test_valid_status_event(self):
        """Test creating a valid status event."""
        from transport_services.kafka.event_models import OrchestratorStatusEvent

        event = OrchestratorStatusEvent(
            request_id="req-123",
            url="https://example.com/page",
            workflow_name="standard_archive_workflow",
            current_step="archive_generation",
            status="in_progress"
        )

        assert event.request_id == "req-123"
        assert event.workflow_name == "standard_archive_workflow"
        assert event.current_step == "archive_generation"
        assert event.status == "in_progress"
        assert event.message is None

    def test_status_event_with_message(self):
        """Test status event with optional message."""
        from transport_services.kafka.event_models import OrchestratorStatusEvent

        event = OrchestratorStatusEvent(
            request_id="req-123",
            url="https://example.com/page",
            workflow_name="standard_archive_workflow",
            current_step="metadata_extraction",
            status="processing",
            message="Extracting metadata from archive"
        )

        assert event.message == "Extracting metadata from archive"

    def test_status_event_json_serialization(self):
        """Test status event JSON serialization."""
        from transport_services.kafka.event_models import OrchestratorStatusEvent

        event = OrchestratorStatusEvent(
            request_id="req-123",
            url="https://example.com/page",
            workflow_name="test_workflow",
            current_step="step1",
            status="in_progress"
        )

        json_str = event.model_dump_json()
        data = json.loads(json_str)

        assert data["workflow_name"] == "test_workflow"
        assert data["current_step"] == "step1"


class TestOrchestratorCompletedEvent:
    """Tests for OrchestratorCompletedEvent."""

    def test_valid_completed_event(self):
        """Test creating a valid completed event."""
        from transport_services.kafka.event_models import OrchestratorCompletedEvent

        event = OrchestratorCompletedEvent(
            request_id="req-123",
            url="https://example.com/page",
            workflow_name="standard_archive_workflow",
            processing_time_seconds=45.5,
            step_results={"archive_path": "/path/to/archive", "doi": "10.1234/test"}
        )

        assert event.request_id == "req-123"
        assert event.workflow_name == "standard_archive_workflow"
        assert event.processing_time_seconds == 45.5
        assert event.step_results["archive_path"] == "/path/to/archive"

    def test_completed_event_processing_time_validation(self):
        """Test that negative processing time raises ValidationError."""
        from transport_services.kafka.event_models import OrchestratorCompletedEvent

        with pytest.raises(ValidationError) as exc_info:
            OrchestratorCompletedEvent(
                request_id="req-123",
                url="https://example.com/page",
                workflow_name="test_workflow",
                processing_time_seconds=-5.0
            )

        assert "processing_time_seconds" in str(exc_info.value)

    def test_completed_event_json_serialization(self):
        """Test completed event JSON serialization."""
        from transport_services.kafka.event_models import OrchestratorCompletedEvent

        event = OrchestratorCompletedEvent(
            request_id="req-123",
            url="https://example.com/page",
            workflow_name="test_workflow",
            processing_time_seconds=30.0,
            step_results={"status": "success"}
        )

        json_str = event.model_dump_json()
        data = json.loads(json_str)

        assert data["processing_time_seconds"] == 30.0
        assert "step_results" in data


class TestOrchestratorFailedEvent:
    """Tests for OrchestratorFailedEvent."""

    def test_valid_failed_event(self):
        """Test creating a valid failed event."""
        from transport_services.kafka.event_models import OrchestratorFailedEvent

        event = OrchestratorFailedEvent(
            request_id="req-123",
            url="https://example.com/page",
            workflow_name="standard_archive_workflow",
            failed_step="archive_generation",
            error_message="Archive generation timeout"
        )

        assert event.request_id == "req-123"
        assert event.workflow_name == "standard_archive_workflow"
        assert event.failed_step == "archive_generation"
        assert event.error_message == "Archive generation timeout"
        assert event.error_details == {}

    def test_failed_event_with_error_details(self):
        """Test failed event with error details."""
        from transport_services.kafka.event_models import OrchestratorFailedEvent

        event = OrchestratorFailedEvent(
            request_id="req-123",
            url="https://example.com/page",
            workflow_name="test_workflow",
            failed_step="metadata_extraction",
            error_message="Extraction failed",
            error_details={"error_code": "TIMEOUT", "retry_count": 3}
        )

        assert event.error_details["error_code"] == "TIMEOUT"
        assert event.error_details["retry_count"] == 3

    def test_failed_event_json_serialization(self):
        """Test failed event JSON serialization."""
        from transport_services.kafka.event_models import OrchestratorFailedEvent

        event = OrchestratorFailedEvent(
            request_id="req-123",
            url="https://example.com/page",
            workflow_name="test_workflow",
            failed_step="step1",
            error_message="Test error"
        )

        json_str = event.model_dump_json()
        data = json.loads(json_str)

        assert data["failed_step"] == "step1"
        assert data["error_message"] == "Test error"
