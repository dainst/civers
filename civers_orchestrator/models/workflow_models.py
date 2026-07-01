"""Workflow state models for CiVers Orchestrator.

These models track the runtime state of workflow execution,
including individual step progress and overall workflow state.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStepStatus(str, Enum):
    """Status values for workflow steps and overall workflow state.

    Attributes:
        PENDING: Step has not started yet
        IN_PROGRESS: Step is currently executing
        COMPLETED: Step completed successfully
        FAILED: Step failed with an error
        TIMEOUT: Step exceeded timeout limit
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class WorkflowStepInstance(BaseModel):
    """Runtime state for a single workflow step.

    Tracks the execution progress of one step in a workflow,
    including timing information and error state.
    """

    name: str = Field(..., description="Step name (matches workflow configuration)")
    status: WorkflowStepStatus = Field(
        default=WorkflowStepStatus.PENDING, description="Current step status"
    )
    started_at: str | None = Field(
        None, description="ISO 8601 timestamp when step started"
    )
    completed_at: str | None = Field(
        None, description="ISO 8601 timestamp when step completed"
    )
    error_message: str | None = Field(
        None, description="Error message if step failed"
    )


class WorkflowInstance(BaseModel):
    """Runtime state for an entire workflow execution.

    Represents a single workflow execution for a specific request,
    tracking all steps and their progress.

    Enhanced for Option B architecture:
    - Tracks completed/failed steps as sets for efficient lookup
    - Stores step results for passing data between steps
    - Includes timing information for monitoring
    - Supports error tracking at workflow level
    """

    request_id: str = Field(..., description="Unique request identifier")
    workflow_name: str = Field(..., description="Name of workflow being executed")
    url: str = Field(..., description="URL being processed")
    status: WorkflowStepStatus = Field(..., description="Overall workflow status")
    steps: list[WorkflowStepInstance] = Field(
        ..., description="List of workflow steps and their status"
    )
    created_at: str = Field(..., description="ISO 8601 timestamp when workflow created")
    updated_at: str = Field(
        ..., description="ISO 8601 timestamp when workflow last updated"
    )
    callback_url: str | None = Field(
        None, description="Optional webhook URL for push notifications"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional workflow metadata"
    )

    # Enhanced fields for Option B architecture
    current_step: str | None = Field(
        None, description="Name of currently executing step"
    )
    completed_steps: set[str] = Field(
        default_factory=set, description="Set of completed step names"
    )
    failed_steps: set[str] = Field(
        default_factory=set, description="Set of failed step names"
    )
    start_time: datetime | None = Field(
        None, description="Datetime when workflow execution started"
    )
    end_time: datetime | None = Field(
        None, description="Datetime when workflow execution ended"
    )
    step_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Results from each completed step (step_name -> result_data)"
    )
    error_message: str | None = Field(
        None, description="Error message if workflow failed"
    )
    failed_at_step: str | None = Field(
        None, description="Step name where workflow failed"
    )

    @property
    def is_complete(self) -> bool:
        """Check if workflow is in a terminal state."""
        return self.status in (WorkflowStepStatus.COMPLETED, WorkflowStepStatus.FAILED)

    @property
    def processing_time_seconds(self) -> float | None:
        """Calculate total processing time if workflow has ended."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def mark_step_completed(self, step_name: str, result_data: dict[str, Any] | None = None) -> None:
        """Mark a step as completed and store its results."""
        self.completed_steps.add(step_name)
        if result_data:
            self.step_results[step_name] = result_data
        self.current_step = None
        self.updated_at = datetime.now(UTC).isoformat()

    def mark_step_failed(self, step_name: str, error_message: str) -> None:
        """Mark a step as failed and record error."""
        self.failed_steps.add(step_name)
        self.failed_at_step = step_name
        self.error_message = error_message
        self.status = WorkflowStepStatus.FAILED
        self.end_time = datetime.now(UTC)
        self.updated_at = datetime.now(UTC).isoformat()

    def mark_workflow_complete(self) -> None:
        """Mark entire workflow as completed."""
        self.status = WorkflowStepStatus.COMPLETED
        self.end_time = datetime.now(UTC)
        self.updated_at = datetime.now(UTC).isoformat()
