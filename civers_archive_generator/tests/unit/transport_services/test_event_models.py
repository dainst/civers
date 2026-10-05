"""Check archive request validation for Kafka events."""

import pytest
from pydantic import ValidationError

from transport_services.event_models import (
    ArchiveCompletedEvent, ArchiveRequestEvent, ArchiveStatusEvent,
)


@pytest.mark.parametrize("field,value", [
    ("request_id", ""),
    ("request_id", "../escape"),
    ("request_id", "bad;id"),
    ("url", "ftp://example.com"),
    ("url", "https://example.com/\n--argument"),
    ("url", "https://example.com/?q='quoted'"),
    ("created_at", "last Tuesday"),
    ("created_at", "2026-09-11T12:00:00Z\n"),
])
def test_invalid_wire_fields_are_rejected(field, value):
    payload = {"request_id": "req-1", "url": "https://example.com/"}
    payload[field] = value
    with pytest.raises(ValidationError):
        ArchiveRequestEvent.model_validate(payload)


def test_wire_request_roundtrips_without_changing_original_url():
    request = ArchiveRequestEvent(request_id="req-1", url="https://example.com")
    restored = ArchiveRequestEvent.model_validate_json(request.model_dump_json())
    assert restored == request
    assert restored.url == "https://example.com"
    assert restored.created_at.endswith("Z")


def test_status_and_duration_are_validated():
    with pytest.raises(ValidationError):
        ArchiveStatusEvent(request_id="req-1", url="https://example.com", status="unknown")
    with pytest.raises(ValidationError):
        ArchiveCompletedEvent(
            request_id="req-1", url="https://example.com", archive_path="/tmp/archive",
            artifacts_created=["warc"], processing_time_seconds=-1,
        )
