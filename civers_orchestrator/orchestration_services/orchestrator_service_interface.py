"""
Interface for Orchestrator Services.

Defines the contract for the core orchestration logic, enabling dependency
injection and better testability by separating transport from logic.
"""

from abc import ABC, abstractmethod

from models.orchestrator_models import StepInstruction, WorkflowStatus, WorkflowTransition
from models.workflow_models import WorkflowInstance


class OrchestratorServiceInterface(ABC):
    """
    Interface for the Orchestrator Service.
    
    This interface defines the contract for any orchestrator implementation.
    It focuses on pure business logic: managing workflow state, resolving
    next steps, and handling step completions/failures.
    """

    @abstractmethod
    def start_workflow(
        self,
        request_id: str,
        url: str,
        workflow_name: str | None = None,
        callback_url: str | None = None,
        metadata: dict | None = None
    ) -> StepInstruction:
        """
        Start a new workflow execution.

        Args:
            request_id: Unique request identifier
            url: URL to process
            workflow_name: Optional explicit workflow name
            callback_url: Optional callback URL for notifications
            metadata: Optional metadata to pass through workflow

        Returns:
            StepInstruction: Instruction for executing the first step
        """
        pass

    @abstractmethod
    def step_completed(
        self,
        request_id: str,
        step_name: str,
        result_data: dict | None = None
    ) -> WorkflowTransition:
        """
        Handle step completion and determine next action.

        Args:
            request_id: Request identifier
            step_name: Name of completed step
            result_data: Optional result data from step

        Returns:
            WorkflowTransition: What to do next
        """
        pass

    @abstractmethod
    def step_failed(
        self,
        request_id: str,
        step_name: str,
        error_message: str
    ) -> WorkflowTransition:
        """
        Handle step failure.

        Args:
            request_id: Request identifier
            step_name: Name of failed step
            error_message: Error message

        Returns:
            WorkflowTransition: Failure transition
        """
        pass

    @abstractmethod
    def get_workflow_state(self, request_id: str) -> WorkflowInstance | None:
        """
        Get current workflow state for a request.

        Args:
            request_id: Request identifier

        Returns:
            WorkflowInstance if found, None otherwise
        """
        pass

    @abstractmethod
    def get_workflow_status(self, request_id: str) -> WorkflowStatus | None:
        """
        Get workflow status for monitoring.

        Args:
            request_id: Request identifier

        Returns:
            WorkflowStatus if found, None otherwise
        """
        pass

    @abstractmethod
    def cleanup_completed_workflows(self, max_age_seconds: int = 3600) -> int:
        """
        Remove old completed/failed workflows.

        Args:
            max_age_seconds: Threshold age in seconds

        Returns:
            Number of workflows removed
        """
        pass

    @abstractmethod
    def check_step_timeout(self, request_id: str) -> WorkflowTransition | None:
        """
        Check if current step has timed out.

        Args:
            request_id: Request identifier

        Returns:
            WorkflowTransition if timeout occurred, None otherwise
        """
        pass

    @abstractmethod
    def check_all_timeouts(self) -> list[WorkflowTransition]:
        """
        Check all active workflows for timeouts.

        Returns:
            List of transitions for timed-out workflows
        """
        pass
