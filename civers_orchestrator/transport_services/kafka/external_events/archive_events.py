"""
Archive Generator Event Models.

Copied from: civers_archive_generator/transport_services/kafka/event_models.py
These models define the events exchanged with the archive_generator service.
"""

from datetime import datetime, timezone
from typing import Any, List, Optional

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
    """Event when someone requests an archive to be created."""

    priority: int = Field(default=1, ge=1, le=10, description="Processing priority")


class ArchiveStatusEvent(EventBaseModel):
    """Event for status updates during processing."""

    status: str = Field(
        ..., description="Current status: processing, completed, or failed"
    )
    message: Optional[str] = Field(None, description="Optional status message")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of the allowed values."""
        valid_statuses = ["processing", "completed", "failed"]
        if v not in valid_statuses:
            raise ValueError(f"status must be one of {valid_statuses}")
        return v


class ArchiveCompletedEvent(EventBaseModel):
    """Event when archive is successfully created."""

    archive_path: str = Field(..., description="Path to the created archive")
    artifacts_created: List[str] = Field(
        ..., description="List of artifacts/files created"
    )
    processing_time_seconds: float = Field(
        ..., description="Time taken to process in seconds"
    )
    snapshot_id: Optional[str] = Field(
        None, description="Snapshot ID from web interface after upload"
    )

    @field_validator("processing_time_seconds", mode="before")
    @classmethod
    def validate_processing_time(cls, v: float) -> float:
        """Validate processing time is non-negative."""
        if v < 0:
            raise ValueError("Processing time must be a non-negative float")
        return v


class ArchiveFailedEvent(EventBaseModel):
    """Event when archive creation fails."""

    error_message: str = Field(..., description="Error message describing the failure")
