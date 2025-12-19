from transport_services.kafka.event_models import ArchiveRequestEvent, ArchiveStatusEvent, ArchiveCompletedEvent, ArchiveFailedEvent, EventBaseModel
import pytest
from pydantic import ValidationError
from dateutil.parser import isoparse

@pytest.mark.unit
@pytest.mark.parametrize("model_cls, kwargs, expected_msg", [
    # ArchiveRequestEvent tests
    (ArchiveRequestEvent, {
        "url": "https://example.com",
        "request_id": "12345",
        "created_at": "01-10-2023 12:00"  # Invalid format
    }, "created_at must be in ISO 8601 UTC format (e.g. '2023-10-01T12:00:00Z')"),

    (ArchiveRequestEvent, {
        "url": "https://example.com",
        "request_id": "12345",
        "created_at": "2023-10-01T12:00:00Z",
        "priority": 0  # Invalid priority
    }, "Input should be greater than or equal to 1"),

    (ArchiveRequestEvent, {
        "url": "https://example.com",
        "request_id": "",  # Invalid request_id
        "created_at": "2023-10-01T12:00:00Z"
    }, "Input should be a valid string non-empty request_id"),

    (ArchiveRequestEvent, {
        "url": "",  # Invalid URL
        "request_id": "12345",
        "created_at": "2023-10-01T12:00:00Z"
    }, "Input should be a valid string non-empty url"),

    # ArchiveStatusEvent tests
    (ArchiveStatusEvent, {
        "request_id": "12345",
        "status": "unknown",  # Invalid status
        "created_at": "2023-10-01T12:00:00Z",
        "url": "https://example.com"
    }, "status must be one of ['processing', 'completed', 'failed']"),

    (ArchiveStatusEvent, {
        "request_id": "12345",
        "status": "processing",
        "created_at": "01-10-2023 12:00",  # Invalid format
        "url": "https://example.com"
    }, "created_at must be in ISO 8601 UTC format (e.g. '2023-10-01T12:00:00Z')"),

    (ArchiveStatusEvent, {
        "request_id": "",  # Invalid request_id
        "status": "processing",
        "created_at": "2023-10-01T12:00:00Z",
        "url": "https://example.com"
    }, "Input should be a valid string non-empty request_id"),

    (ArchiveStatusEvent, {
        "request_id": "12345",
        "status": "processing",
        "created_at": "2023-10-01T12:00:00Z",
        "url": ""  # Invalid URL
    }, "Input should be a valid string non-empty url"),
    # ArchiveCompletedEvent tests
    (ArchiveCompletedEvent, {
        "request_id": "12345",
        "url": "https://example.com",
        "archive_path": "/path/to/archive",
        "artifacts_created": ["warc", "screenshot"],
        "processing_time_seconds": -1.0,  # Invalid processing time
        "created_at": "2023-10-01T12:00:00Z"
    }, "Processing time must be a non-negative float"),
    (ArchiveCompletedEvent, {
        "request_id": "12345",
        "url": "https://example.com",
        "archive_path": "/path/to/archive",
        "artifacts_created": ["warc", "screenshot"],
        "processing_time_seconds": 5.0,
        "created_at": "01-10-2023 12:00"  # Invalid format
    }, "created_at must be in ISO 8601 UTC format (e.g. '2023-10-01T12:00:00Z')"),
    (ArchiveCompletedEvent, {
        "request_id": "",  # Invalid request_id
        "url": "https://example.com",
        "archive_path": "/path/to/archive",
        "artifacts_created": ["warc", "screenshot"],
        "processing_time_seconds": 5.0,
        "created_at": "2023-10-01T12:00:00Z"
    }, "Input should be a valid string non-empty request_id"),
    (ArchiveFailedEvent, {
        "request_id": "",# Invalid request_id
        "url": "https://example.com",
        "error_message": "Failed to create archive",
        "created_at": "2023-10-01T12:00:00Z"
    }, "Input should be a valid string non-empty request_id"),
    (ArchiveFailedEvent, {
        "request_id": "12345",
        "url": "",  # Invalid URL
        "error_message": "Failed to create archive",
        "created_at": "2023-10-01T12:00:00Z"
    }, "Input should be a valid string non-empty url"),
    (ArchiveFailedEvent, {
        "request_id": "12345",
        "url": "https://example.com",
        "error_message": "Failed to create archive",
        "created_at": "01-10-2023 12:00"  # Invalid format
    }, "created_at must be in ISO 8601 UTC format (e.g. '2023-10-01T12:00:00Z')")
    

])
@pytest.mark.unit
def test_event_model_validation_errors(model_cls, kwargs, expected_msg):
    with pytest.raises(ValidationError) as e:
        model_cls(**kwargs)
    assert expected_msg in e.value.errors()[0]['msg']

@pytest.mark.unit
def test_event_base_model_default_created_at(model_cls, kwargs, expected_msg):
    
    with pytest.raises(ValidationError) as e:
        model_cls(**kwargs)
    assert expected_msg in e.value.errors()[0]['msg']


@pytest.mark.unit
def test_event_base_model_default_created_at():
    event_base_model= EventBaseModel(**{"request_id": "12345", "url": "https://example.com"})
    #validate the create format is correct
    assert event_base_model.created_at is not None
    #validate the created_at is in ISO 8601 format
    assert isinstance(event_base_model.created_at, str)
    #validate the created_at is in UTC format
    assert event_base_model.created_at.endswith("Z")
    #validate the created_at is in ISO 8601 format
    assert isoparse(event_base_model.created_at) , "Created at should be in ISO 8601 format"


#wite a test function to validate the event models
@pytest.mark.unit
def test_event_model_valid_archive_request_event():
    event = ArchiveRequestEvent(url="https://example.com", request_id="12345",        created_at="2023-10-01T12:00:00Z")
    assert event.url == "https://example.com"
    assert event.priority == 1 , "Default priority should be 1"
    assert event.request_id == "12345"
    assert isoparse(event.created_at) , "Created at should be in ISO 8601 format"

@pytest.mark.unit
def test_event_model_valid_archive_status_event():
    event = ArchiveStatusEvent(
        request_id="12345",
        status="processing",
        message="Processing started",
        created_at="2023-10-01T12:00:00Z",
        url="https://example.com"
    )
    assert event.request_id == "12345"
    assert event.status == "processing"
    assert event.message == "Processing started"
    assert isoparse(event.created_at) , "Created at should be in ISO 8601 format"

#missing request_id or created_at
@pytest.mark.unit
def test_event_model_valid_archive_completed_event():
    event = ArchiveCompletedEvent(
        request_id="12345",
        url="https://example.com",
        archive_path="/path/to/archive",
        artifacts_created=["warc", "screenshot"],
        processing_time_seconds=5.0,
        created_at="2023-10-01T12:00:00Z"
    )
    assert event.request_id == "12345"
    assert event.url == "https://example.com"
    assert event.archive_path == "/path/to/archive"
    assert event.artifacts_created == ["warc", "screenshot"]
    assert event.processing_time_seconds == 5.0
    assert isoparse(event.created_at) , "Created at should be in ISO 8601 format"
