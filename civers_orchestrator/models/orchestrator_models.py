"""
Orchestrator Data Models.

This module defines the data structures used for communication between
OrchestratorService and KafkaTransportService.

Key Principle:
- OrchestratorService returns these models (instructions/transitions)
- KafkaTransportService executes them (creates and publishes events)
- Clear separation: Business logic vs Transport layer
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from configs.models import WorkflowStepConfig
from models.workflow_models import WorkflowInstance


@dataclass
class StepInstruction:
    """
    Transport-agnostic instruction from orchestrator to transport layer.

    This is what the orchestrator returns when starting a workflow or moving to
    the next step. It contains ONLY transport-agnostic information:
    - Which component to invoke
    - What data schema to use
    - What data to include

    The transport layer uses a TransportAdapter to translate this instruction
    into transport-specific operations (e.g., Kafka topics/events, REST endpoints).

    Example:
        instruction = StepInstruction(
            step_config=archive_step_config,
            request_id="req-123",
            url="https://example.com",
            component="archive_generator",
            input_schema="ArchiveRequest",
            input_data={"priority": 1}
        )
    """

    step_config: WorkflowStepConfig
    request_id: str
    url: str
    component: str  # Component identifier (transport-agnostic)
    input_schema: str  # Data schema name (not event model)
    input_data: Dict[str, Any] = field(default_factory=dict)
    workflow_instance: WorkflowInstance = field(default=None)  # Reference to full instance
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowTransition:
    """
    Result of a workflow state transition.

    This is what the orchestrator returns after a step completes or fails.
    It tells the transport layer what action to take next:

    Actions:
    - "execute_step": Execute the next step (includes StepInstruction)
    - "workflow_complete": Workflow finished successfully (publish completion event)
    - "workflow_failed": Workflow failed (publish failure event)

    Example - Next Step:
        transition = WorkflowTransition(
            action="execute_step",
            request_id="req-123",
            step_instruction=StepInstruction(...)
        )

    Example - Completion:
        transition = WorkflowTransition(
            action="workflow_complete",
            request_id="req-123",
            workflow_instance=completed_instance
        )

    Example - Failure:
        transition = WorkflowTransition(
            action="workflow_failed",
            request_id="req-123",
            workflow_instance=failed_instance,
            error_message="Archive generation failed",
            failed_step="archive_generation"
        )
    """

    action: str  # "execute_step", "workflow_complete", "workflow_failed"
    request_id: str
    step_instruction: Optional[StepInstruction] = None
    workflow_instance: Optional[WorkflowInstance] = None
    error_message: Optional[str] = None
    failed_step: Optional[str] = None

    def __post_init__(self):
        """Validate transition based on action."""
        if self.action == "execute_step" and not self.step_instruction:
            raise ValueError("execute_step action requires step_instruction")

        if self.action in ("workflow_complete", "workflow_failed") and not self.workflow_instance:
            raise ValueError(f"{self.action} action requires workflow_instance")

        if self.action == "workflow_failed" and not self.error_message:
            raise ValueError("workflow_failed action requires error_message")

        if self.action not in ("execute_step", "workflow_complete", "workflow_failed"):
            raise ValueError(f"Invalid action: {self.action}")


@dataclass
class WorkflowStatus:
    """
    Current status of a workflow execution.

    Used for status queries and monitoring. Provides a snapshot of workflow state
    without exposing the full WorkflowInstance internals.

    Example:
        status = WorkflowStatus(
            request_id="req-123",
            workflow_name="standard_archive_workflow",
            url="https://example.com",
            current_step="metadata_extraction",
            completed_steps={"archive_generation"},
            total_steps=3,
            status="in_progress"
        )
    """

    request_id: str
    workflow_name: str
    url: str
    current_step: Optional[str]
    completed_steps: set[str]
    total_steps: int
    status: str  # "pending", "in_progress", "completed", "failed"
    error_message: Optional[str] = None
    failed_step: Optional[str] = None

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage based on completed steps."""
        if self.total_steps == 0:
            return 0.0
        return (len(self.completed_steps) / self.total_steps) * 100

    @property
    def is_complete(self) -> bool:
        """Check if workflow is in a terminal state."""
        return self.status in ("completed", "failed")
