"""
Archive Generator Event Models.

These models define the events exchanged with the archive_generator service.
"""


from pydantic import Field, field_validator

from transport_services.kafka.event_models import EventBaseModel


class ArchiveRequestEvent(EventBaseModel):
    """Event when someone requests an archive to be created."""

    priority: int = Field(default=1, ge=1, le=10, description="Processing priority")


class ArchiveStatusEvent(EventBaseModel):
    """Event for status updates during processing."""

    status: str = Field(
        ..., description="Current status: processing, completed, or failed"
    )
    message: str | None = Field(None, description="Optional status message")

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
    artifacts_created: list[str] = Field(
        ..., description="List of artifacts/files created"
    )
    processing_time_seconds: float = Field(
        ..., description="Time taken to process in seconds"
    )
    snapshot_id: str | None = Field(
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
