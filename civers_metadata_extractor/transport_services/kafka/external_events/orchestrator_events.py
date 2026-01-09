"""
Orchestrator Event Models.

Copied from: civers_orchestrator/transport_services/kafka/event_models.py
These models define the events exchanged with the orchestrator service.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
import re


class EventBaseModel(BaseModel):
    """Base model for orchestrator events."""

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


class OrchestratorRequestEvent(EventBaseModel):
    """Event model for general orchestrator requests."""

    workflow_name: Optional[str] = Field(
        None, description="Workflow name to execute (auto-detect if None)"
    )
    priority: int = Field(default=1, ge=1, le=10, description="Processing priority (1-10)")
    callback_url: Optional[str] = Field(
        None, description="Optional webhook URL for status updates"
    )


class OrchestratorStatusEvent(EventBaseModel):
    """Event model for orchestrator status updates."""

    workflow_name: str = Field(..., description="Name of the workflow")
    current_step: str = Field(..., description="Current step name")
    status: str = Field(..., description="Current status (in_progress, completed, failed)")
    message: Optional[str] = Field(None, description="Optional status message")


class OrchestratorCompletedEvent(EventBaseModel):
    """Event model for successful workflow completion."""

    workflow_name: str = Field(..., description="Name of the workflow")
    completed_steps: List[str] = Field(..., description="List of completed step names")
    processing_time_seconds: float = Field(..., ge=0.0, description="Total processing time")
    step_results: Dict[str, Any] = Field(default_factory=dict, description="Results from each step")


class OrchestratorFailedEvent(EventBaseModel):
    """Event model for workflow failures."""

    workflow_name: str = Field(..., description="Name of the workflow")
    failed_step: str = Field(..., description="Name of the step that failed")
    error_message: str = Field(..., description="Error message describing the failure")
    error_details: Dict[str, Any] = Field(default_factory=dict, description="Additional error info")
    completed_steps: List[str] = Field(default_factory=list, description="Steps completed before failure")
