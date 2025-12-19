"""Custom exceptions for orchestration services.

This module defines domain-specific exceptions used throughout the
orchestration services to provide clear error handling and messaging.
"""


class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected in workflow steps.

    This occurs when workflow steps have a dependency cycle that would
    prevent proper execution order determination using topological sorting.

    Example:
        Step A depends on Step B
        Step B depends on Step C
        Step C depends on Step A  # ← Circular dependency!

    Attributes:
        message: Error message describing the circular dependency
        steps: Optional list of step names involved in the cycle
    """

    def __init__(self, message: str, steps: list = None):
        """Initialize circular dependency error.

        Args:
            message: Error message
            steps: Optional list of steps involved in circular dependency
        """
        super().__init__(message)
        self.steps = steps or []


class WorkflowNotFoundError(Exception):
    """Raised when a requested workflow name is not found in configuration.

    This occurs when attempting to access a workflow that doesn't exist
    in the loaded workflow configurations.

    Attributes:
        workflow_name: Name of the workflow that was not found
        available_workflows: List of available workflow names
    """

    def __init__(self, workflow_name: str, available_workflows: list = None):
        """Initialize workflow not found error.

        Args:
            workflow_name: Name of workflow that was not found
            available_workflows: Optional list of available workflow names
        """
        message = f"Workflow '{workflow_name}' not found in configuration"
        if available_workflows:
            message += f". Available workflows: {available_workflows}"
        super().__init__(message)
        self.workflow_name = workflow_name
        self.available_workflows = available_workflows or []
