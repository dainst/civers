"""Timeout monitoring and detection for workflow steps.

This module provides timeout monitoring capabilities to detect and handle
workflow steps that exceed their configured timeout limits.
"""

from datetime import UTC, datetime

from configs.logging_config import get_logger
from configs.models import WorkflowConfig
from models.workflow_models import WorkflowStepStatus
from orchestration_services.workflow_state_store import WorkflowStateStore

logger = get_logger(__name__)


class TimeoutMonitor:
    """Monitors workflow steps for timeout violations.

    This class checks whether workflow steps have exceeded their configured
    timeout limits and provides mechanisms for batch timeout checking across
    all active workflows.

    Attributes:
        state_store: Workflow state storage
        workflows: Dictionary of workflow configurations
    """

    def __init__(
        self,
        state_store: WorkflowStateStore,
        workflows: dict[str, WorkflowConfig]
    ):
        """Initialize timeout monitor.

        Args:
            state_store: Workflow state store for accessing workflow instances
            workflows: Dictionary mapping workflow names to configurations
        """
        self.state_store = state_store
        self.workflows = workflows
        logger.info("✅ TimeoutMonitor initialized")

    def check_step_timeout(self, request_id: str) -> dict | None:
        """Check if current step has exceeded its timeout.

        Args:
            request_id: Request identifier

        Returns:
            Dict with timeout information if timeout occurred, None otherwise.
            Dict contains: request_id, step_name, elapsed_seconds, timeout_seconds
        """
        workflow_instance = self.state_store.get_workflow(request_id)
        if not workflow_instance:
            return None

        # Find currently executing step
        current_step_name = workflow_instance.current_step
        if not current_step_name:
            return None

        # Get step config
        if workflow_instance.workflow_name not in self.workflows:
            logger.warning(
                f"Workflow '{workflow_instance.workflow_name}' not found "
                f"while checking timeout for request {request_id}"
            )
            return None

        workflow = self.workflows[workflow_instance.workflow_name]
        step_config = next(
            (s for s in workflow.steps if s.name == current_step_name),
            None
        )

        if not step_config:
            return None

        # Find step instance
        step_instance = next(
            (s for s in workflow_instance.steps if s.name == current_step_name),
            None
        )

        if not step_instance or not step_instance.started_at:
            return None

        # Check timeout
        try:
            started = datetime.fromisoformat(
                step_instance.started_at.replace('Z', '+00:00')
            )
        except ValueError:
            logger.warning(
                f"Invalid started_at timestamp for step {current_step_name}"
            )
            return None

        elapsed = (datetime.now(UTC) - started).total_seconds()

        if elapsed > step_config.timeout_seconds:
            logger.error(
                f"⏱️ Step '{current_step_name}' timed out after {elapsed:.1f}s "
                f"(limit: {step_config.timeout_seconds}s) for request {request_id}"
            )

            # Mark step as timed out
            step_instance.status = WorkflowStepStatus.TIMEOUT
            step_instance.error_message = (
                f"Step exceeded timeout of {step_config.timeout_seconds}s "
                f"(actual: {elapsed:.1f}s)"
            )

            return {
                "request_id": request_id,
                "step_name": current_step_name,
                "elapsed_seconds": elapsed,
                "timeout_seconds": step_config.timeout_seconds,
                "error_message": step_instance.error_message
            }

        return None

    def check_all_timeouts(self) -> list[dict]:
        """Check all active workflows for timeouts.

        Returns:
            List of timeout information dicts for timed-out workflows
        """
        timeouts = []

        # Get all active workflow request IDs
        active_workflows = self.state_store.get_all_active()

        for request_id in active_workflows:
            timeout_info = self.check_step_timeout(request_id)
            if timeout_info:
                timeouts.append(timeout_info)

        if timeouts:
            logger.warning(f"⏱️ Detected {len(timeouts)} timed-out workflows")

        return timeouts
