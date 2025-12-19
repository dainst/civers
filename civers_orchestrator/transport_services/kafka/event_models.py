"""Event models for Kafka transport service in CiVers Orchestrator."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class EventBaseModel(BaseModel):
    """Base model for all events in the orchestrator.

    Following the CiVers pattern:
    - request_id: REQUIRED - provided by external caller
    - created_at: Auto-generated ISO 8601 UTC timestamp (can be overridden)
    - url: REQUIRED - the URL being processed
    """

    request_id: str = Field(..., description="Unique identifier for the request")
    # immutable timestamp in ISO 8601 UTC format, should not be changed after creation
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


class OrchestratorRequestEvent(EventBaseModel):
    """Event when an external system requests orchestration workflow.

    This is the entry point event that triggers a workflow execution.
    External systems provide request_id, and optionally specify workflow.
    """

    workflow_name: Optional[str] = Field(
        None, description="Workflow name to execute (if None, inferred from domain)"
    )
    priority: int = Field(
        default=1, ge=1, le=10, description="Processing priority (1=low, 10=high)"
    )
    callback_url: Optional[str] = Field(
        None,
        description="Optional webhook URL for push notifications (status, completion, failure)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional request metadata"
    )


class OrchestratorStatusEvent(EventBaseModel):
    """Event for workflow status updates during processing.

    Published when workflow progresses through steps or changes state.
    """

    workflow_name: str = Field(..., description="Workflow being executed")
    current_step: str = Field(..., description="Current workflow step being executed")
    status: str = Field(..., description="Current status (e.g. 'in_progress', 'processing')")
    message: Optional[str] = Field(None, description="Optional status message")


class OrchestratorCompletedEvent(EventBaseModel):
    """Event when workflow completes successfully.

    Contains final results from all workflow steps.
    """

    workflow_name: str = Field(..., description="Workflow that was executed")
    processing_time_seconds: float = Field(
        ..., description="Total workflow processing time in seconds"
    )
    completed_steps: list[str] = Field(
        default_factory=list, description="List of steps that were successfully completed"
    )
    results: Dict[str, Any] = Field(
        default_factory=dict, description="Aggregated results from all workflow steps",
        alias="step_results"
    )

    model_config = {"populate_by_name": True}

    @field_validator("processing_time_seconds")
    @classmethod
    def validate_processing_time(cls, v: float) -> float:
        """Validate processing time is non-negative."""
        if v < 0:
            raise ValueError("processing_time_seconds must be non-negative")
        return v


class OrchestratorFailedEvent(EventBaseModel):
    """Event when workflow fails at any step.

    Contains error information and the step where failure occurred.
    """

    workflow_name: str = Field(..., description="Workflow that failed")
    failed_step: str = Field(..., description="Step where workflow failed")
    error_message: str = Field(..., description="Error message describing the failure")
    error_details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional error details"
    )
