"""Kafka request, status, completion and failure events."""

from pydantic import BaseModel, Field,field_validator
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import re

from civers_common import is_valid_request_id
class EventBaseModel(BaseModel):
    """Common event fields: request ID, timestamp, URL and metadata."""
    request_id: str = Field(..., description="Unique identifier for the request")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        description="The timestamp when the event was created, in ISO 8601 UTC format"
    )
    url: str = Field(..., description="The URL associated with the event")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional request metadata")
    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Require letters, digits, hyphens and underscores in request IDs."""
        if not v or v.strip() == "":
            raise ValueError("Input should be a valid string non-empty request_id")
        
        # Use the same request ID rules as the shared Kafka transport.
        if not is_valid_request_id(v):
            raise ValueError("request_id must contain only alphanumeric characters, hyphens, and underscores")
            
        return v

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at_format(cls, v: Any) -> Any:
        """Require timestamp strings in YYYY-MM-DDTHH:MM:SSZ format."""
        if isinstance(v, str):
            # Match the whole string to reject trailing newlines.
            iso8601_utc_regex = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
            if not re.fullmatch(iso8601_utc_regex, v):
                raise ValueError("created_at must be in ISO 8601 UTC format (e.g. '2023-10-01T12:00:00Z')")
        return v
    @field_validator("url")
    def validate_url(cls, v: str) -> str:
        """Require an HTTP(S) URL string without whitespace, quotes or markup characters."""
        if not v or v.strip() == "":
            raise ValueError("Input should be a valid string non-empty url")
        
        if not re.fullmatch(r"https?://[^\s/$.?#].[^\s]*", v):
            raise ValueError("URL must be a valid http or https address")

        if any(char in v for char in ['\n', '\r', '\t', '<', '>', '"', "'"]):
            raise ValueError("URL contains prohibited characters")

        return v
    
class ArchiveRequestEvent(EventBaseModel):
    """Archive request using the common event fields. Extra fields are ignored."""

class ArchiveStatusEvent(EventBaseModel):
    """Event for status updates during processing."""
    status: str  # "processing", "completed", "failed"
    message: Optional[str] = None
    @field_validator("status")
    def validate_status(cls, v):
        """Reject any status but "processing", "completed" or "failed"."""
        valid_statuses = ["processing", "completed", "failed"]
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
        return v

class ArchiveCompletedEvent(EventBaseModel):
    """Event for a capture with successful artifacts, even when upload failed.

    status is complete when all requested artifacts exist, or partial otherwise.
    """
    archive_path: str
    artifacts_created: List[str]
    processing_time_seconds: float
    snapshot_id: Optional[str] = None  # API snapshot ID, or the local capture folder name.
    status: str = "complete"  # "complete" | "partial"
    failed_artifacts: List[str] = Field(default_factory=list)
    missing_artifacts: List[str] = Field(default_factory=list)  # requested, never reported
    skipped_generators: List[str] = Field(default_factory=list)  # configured, could not run
    @field_validator("processing_time_seconds", mode="before")
    @classmethod
    def validate_processing_time(cls, v: float) -> float:
        """Reject a negative duration."""
        if v < 0:
            raise ValueError("Processing time must be a non-negative float")
        return v

class ArchiveFailedEvent(EventBaseModel):
    """Event when archive creation fails."""
    error_message: str
    error_type: Optional[str] = None  # e.g., 'missing_required_artifacts', 'configuration_not_found'
    archive_path: Optional[str] = None  # Capture folder, if one was created.
    artifacts_created: List[str] = Field(default_factory=list)  # Successful artifacts
    failed_artifacts: List[str] = Field(default_factory=list)  # Failed artifacts
    missing_artifacts: List[str] = Field(default_factory=list)  # Requested artifacts with no reported result.
    processing_time_seconds: Optional[float] = None