"""
Archive Generator Event Models.

Copied from: civers_archive_generator/transport_services/kafka/event_models.py
These models define the events exchanged with the archive_generator service.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
import re


class EventBaseModel(BaseModel):
    """Base model for archive generator events."""

    request_id: str = Field(..., description="Unique identifier for the request")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        description="The timestamp when the event was created, in ISO 8601 UTC format",
    )
    url: str = Field(..., description="The URL associated with the event")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional request metadata")

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Validate request_id is not empty or whitespace."""
        if not v or v.strip() == "":
            raise ValueError("Input should be a valid string non-empty request_id")
        return v

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at_format(cls, v: Any) -> Any:
        """Validate created_at is in ISO 8601 UTC format."""
        if isinstance(v, str):
            iso8601_utc_regex = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
            if not re.match(iso8601_utc_regex, v):
                raise ValueError(
                    "created_at must be in ISO 8601 UTC format (e.g. '2023-10-01T12:00:00Z')"
                )
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate url is not empty or whitespace."""
        if not v or v.strip() == "":
            raise ValueError("Input should be a valid string non-empty url")
        return v


class ArchiveRequestEvent(EventBaseModel):
    """Event model for archive requests."""

    priority: int = Field(default=1, description="Processing priority (1=normal, 2=high, 3=urgent)")


class ArchiveStatusEvent(EventBaseModel):
    """Event model for archive generation status updates."""

    status: str = Field(..., description="Current status (processing, completed, failed)")
    message: str = Field(..., description="Human-readable status message")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status."""
        valid_statuses = ["processing", "completed", "failed"]
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
        return v


class ArchiveCompletedEvent(EventBaseModel):
    """Event model for successful archive generation completion."""

    archive_path: str = Field(..., description="Path to the generated archive file")
    artifacts_created: List[str] = Field(..., description="List of created artifact types")
    processing_time_seconds: float = Field(..., description="Time taken to create archive")
    snapshot_id: Optional[str] = Field(None, description="Optional snapshot ID from storage")


class ArchiveFailedEvent(EventBaseModel):
    """Event model for failed archive generation attempts."""

    error_message: str = Field(..., description="Error message describing the failure")
