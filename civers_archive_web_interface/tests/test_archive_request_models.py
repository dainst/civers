"""
Unit tests for Archive Request models after workflow_name removal.
"""

import pytest
from pydantic import ValidationError
from app.models.archive_request_events import OrchestratorRequestEvent, ArchiveRequestForm

class TestArchiveRequestModels:
    """Test cases for models used in archive request flow."""

    def test_orchestrator_request_event_creation_valid(self):
        """Test creating a valid OrchestratorRequestEvent without workflow_name."""
        event = OrchestratorRequestEvent(
            request_id="abc-123",
            url="https://example.com/page",
            callback_url="http://web-interface/api/webhook/status",
            priority=2,
            metadata={"source": "test"}
        )
        
        assert event.request_id == "abc-123"
        assert event.url == "https://example.com/page"
        assert event.callback_url == "http://web-interface/api/webhook/status"
        assert event.priority == 2
        assert event.metadata == {"source": "test"}
        
        # Verify workflow_name is NOT in model_dump
        data = event.model_dump()
        assert "workflow_name" not in data
        assert "request_id" in data
        assert "url" in data
        assert "priority" in data

    def test_orchestrator_request_event_invalid_url(self):
        """Test URL validation in OrchestratorRequestEvent."""
        with pytest.raises(ValidationError):
            OrchestratorRequestEvent(
                request_id="abc-123",
                url="invalid-url"
            )

    def test_archive_request_form_valid(self):
        """Test ArchiveRequestForm validation."""
        form = ArchiveRequestForm(
            url="https://example.com",
            domain="example.com"
        )
        assert form.url == "https://example.com"
        assert form.domain == "example.com"

    def test_archive_request_form_invalid(self):
        """Test ArchiveRequestForm invalid inputs."""
        # Empty URL
        with pytest.raises(ValidationError):
            ArchiveRequestForm(url="", domain="example.com")
        
        # Invalid URL scheme
        with pytest.raises(ValidationError):
            ArchiveRequestForm(url="ftp://example.com", domain="example.com")
        
        # Empty domain
        with pytest.raises(ValidationError):
            ArchiveRequestForm(url="https://example.com", domain="")

from app.api.webhook import WebhookPayload

class TestWebhookPayload:
    """Test cases for WebhookPayload model."""

    def test_webhook_payload_valid_with_workflow(self):
        """Test WebhookPayload with workflow_name."""
        payload = WebhookPayload(
            request_id="abc-123",
            url="https://example.com",
            workflow_name="standard_archive",
            status="in_progress"
        )
        assert payload.workflow_name == "standard_archive"
        assert payload.status == "in_progress"

    def test_webhook_payload_valid_without_workflow(self):
        """Test WebhookPayload without workflow_name (optional)."""
        payload = WebhookPayload(
            request_id="abc-123",
            url="https://example.com",
            status="completed"
        )
        assert payload.workflow_name is None
        assert payload.status == "completed"
