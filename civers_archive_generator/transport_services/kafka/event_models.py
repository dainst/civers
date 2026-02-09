from pydantic import BaseModel, Field,field_validator
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import re
class EventBaseModel(BaseModel):
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
        if not v or v.strip() == "":
            raise ValueError("Input should be a valid string non-empty request_id")
        return v

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at_format(cls, v: Any) -> Any:
        if isinstance(v, str):
            iso8601_utc_regex = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
            if not re.match(iso8601_utc_regex, v):
                raise ValueError("created_at must be in ISO 8601 UTC format (e.g. '2023-10-01T12:00:00Z')")
        return v
    @field_validator("url")
    def validate_url(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Input should be a valid string non-empty url")
        return v
    
class ArchiveRequestEvent(EventBaseModel):
    """Event when someone requests an archive to be created."""
    priority: int = Field(default=1, ge=1, le=10)

class ArchiveStatusEvent(EventBaseModel):
    """Event for status updates during processing."""
    status: str  # "processing", "completed", "failed"
    message: Optional[str] = None
    @field_validator("status")
    def validate_status(cls, v):
        valid_statuses = ["processing", "completed", "failed"]
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
        return v

class ArchiveCompletedEvent(EventBaseModel):
    """Event when archive is successfully created."""
    archive_path: str
    artifacts_created: List[str]
    processing_time_seconds: float
    snapshot_id: Optional[str] = None  # Snapshot ID from web interface after upload
    @field_validator("processing_time_seconds", mode="before")
    @classmethod
    def validate_processing_time(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Processing time must be a non-negative float")
        return v

class ArchiveFailedEvent(EventBaseModel):
    """Event when archive creation fails."""
    error_message: str
    error_type: Optional[str] = None  # e.g., 'missing_required_artifacts', 'configuration_not_found'
    archive_path: Optional[str] = None  # Path to partial archive (if any)
    artifacts_created: List[str] = Field(default_factory=list)  # Successful artifacts
    failed_artifacts: List[str] = Field(default_factory=list)  # Failed artifacts
    missing_artifacts: List[str] = Field(default_factory=list)  # Required but not created
    processing_time_seconds: Optional[float] = None