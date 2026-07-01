"""Thread-safe workflow state storage with memory management.

This module provides centralized workflow state management with:
- Thread-safe access using RLock
- Automatic memory cleanup of old workflows
- Configurable storage limits
- Bulk query operations
"""

import threading
from datetime import UTC, datetime

from configs.logging_config import get_logger
from models.workflow_models import WorkflowInstance, WorkflowStepStatus

logger = get_logger(__name__)


class WorkflowStateStore:
    """Thread-safe storage for workflow execution states.

    This class manages the in-memory storage of workflow instances with:
    - Thread-safe read/write operations using RLock
    - Automatic cleanup of completed workflows
    - Configurable maximum storage limits
    - Memory management to prevent unbounded growth

    Attributes:
        max_stored_workflows: Maximum number of workflows to store
        workflow_states: Dictionary mapping request_id to WorkflowInstance
    """

    def __init__(self, max_stored_workflows: int = 10000):
        """Initialize workflow state store.

        Args:
            max_stored_workflows: Maximum number of workflows to keep in memory
        """
        self.max_stored_workflows = max_stored_workflows
        self.workflow_states: dict[str, WorkflowInstance] = {}
        self._state_lock = threading.RLock()  # Reentrant lock for thread safety

        logger.info(
            f"✅ WorkflowStateStore initialized with max limit: {max_stored_workflows}"
        )

    def store_workflow(self, request_id: str, workflow: WorkflowInstance) -> None:
        """Store a workflow instance with thread safety and limit enforcement.

        Args:
            request_id: Unique request identifier
            workflow: Workflow instance to store

        Raises:
            ValueError: If request_id is empty or workflow is None
        """
        if not request_id:
            raise ValueError("request_id cannot be empty")
        if workflow is None:
            raise ValueError("workflow cannot be None")

        with self._state_lock:
            self.workflow_states[request_id] = workflow
            self._enforce_workflow_limit()

        logger.debug(f"Stored workflow for request {request_id}")

    def get_workflow(self, request_id: str) -> WorkflowInstance | None:
        """Retrieve a workflow instance by request ID.

        Args:
            request_id: Request identifier

        Returns:
            WorkflowInstance if found, None otherwise
        """
        with self._state_lock:
            return self.workflow_states.get(request_id)

    def update_workflow(self, request_id: str, workflow: WorkflowInstance) -> None:
        """Update an existing workflow instance.

        Args:
            request_id: Request identifier
            workflow: Updated workflow instance

        Raises:
            ValueError: If workflow doesn't exist for request_id
        """
        with self._state_lock:
            if request_id not in self.workflow_states:
                raise ValueError(f"Workflow not found for request_id: {request_id}")

            self.workflow_states[request_id] = workflow

        logger.debug(f"Updated workflow for request {request_id}")

    def remove_workflow(self, request_id: str) -> bool:
        """Remove a workflow from storage.

        Args:
            request_id: Request identifier

        Returns:
            True if workflow was removed, False if not found
        """
        with self._state_lock:
            if request_id in self.workflow_states:
                del self.workflow_states[request_id]
                logger.debug(f"Removed workflow for request {request_id}")
                return True

        return False

    def cleanup_completed_workflows(self, max_age_seconds: int = 3600) -> int:
        """Remove completed/failed workflows older than specified age.

        This method removes workflows that have been in a terminal state
        (completed or failed) for longer than the specified age, helping
        to manage memory usage over time.

        Args:
            max_age_seconds: Remove workflows completed this long ago (default: 1 hour)

        Returns:
            Number of workflows removed
        """
        now = datetime.now(UTC)
        removed = 0

        with self._state_lock:
            to_remove = []
            for request_id, workflow in self.workflow_states.items():
                if workflow.is_complete and workflow.end_time:
                    age = (now - workflow.end_time).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(request_id)

            for request_id in to_remove:
                del self.workflow_states[request_id]
                removed += 1

        if removed > 0:
            logger.info(f"🧹 Cleaned up {removed} completed workflows")

        return removed

    def get_all_active(self) -> list[str]:
        """Get list of request IDs for all active workflows.

        Returns:
            List of request IDs for workflows that are currently in progress
        """
        with self._state_lock:
            return [
                request_id
                for request_id, wf in self.workflow_states.items()
                if wf.status == WorkflowStepStatus.IN_PROGRESS
            ]

    def get_all_with_status(self, status: WorkflowStepStatus) -> list[str]:
        """Get list of request IDs for workflows with specific status.

        Args:
            status: Workflow status to filter by

        Returns:
            List of request IDs matching the status
        """
        with self._state_lock:
            return [
                request_id
                for request_id, wf in self.workflow_states.items()
                if wf.status == status
            ]

    def get_count_by_status(self) -> dict[str, int]:
        """Get count of workflows grouped by status.

        Returns:
            Dictionary mapping status names to counts
        """
        with self._state_lock:
            counts: dict[str, int] = {}
            for workflow in self.workflow_states.values():
                status = workflow.status.value
                counts[status] = counts.get(status, 0) + 1

            return counts

    def get_total_count(self) -> int:
        """Get total number of workflows in storage.

        Returns:
            Total count of stored workflows
        """
        with self._state_lock:
            return len(self.workflow_states)

    def _enforce_workflow_limit(self) -> None:
        """Enforce maximum number of stored workflows.

        Removes oldest completed workflows when storage limit is reached.
        This is an internal method called automatically on workflow storage.
        """
        if len(self.workflow_states) >= self.max_stored_workflows:
            # Get completed workflows sorted by end time
            completed = [
                (wf.end_time, request_id)
                for request_id, wf in self.workflow_states.items()
                if wf.is_complete and wf.end_time
            ]

            if completed:
                completed.sort()  # Oldest first
                # Remove 10% of completed workflows
                to_remove = max(1, len(completed) // 10)
                for _, request_id in completed[:to_remove]:
                    del self.workflow_states[request_id]

                logger.warning(
                    f"⚠️ Workflow limit reached ({self.max_stored_workflows}), "
                    f"removed {to_remove} oldest workflows"
                )
