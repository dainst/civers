"""Workflow resolution and dependency management.

This module provides workflow resolution capabilities including:
- Domain-to-workflow matching with three-tier strategy
- Dependency resolution using topological sorting (Kahn's algorithm)
- Workflow navigation (first step, next step, completion checking)
"""

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set

from civers_common import ConfigurationError, DomainResolutionMixin

from configs.logging_config import get_logger
from configs.models import DomainConfig, WorkflowConfig, WorkflowStepConfig
from orchestration_services.exceptions import CircularDependencyError, WorkflowNotFoundError

logger = get_logger(__name__)


class WorkflowResolver(DomainResolutionMixin):
    """Resolves workflows, dependencies, and step navigation.

    This class provides all workflow resolution logic:
    - Matching URLs to workflows based on domain configuration
    - Resolving step dependencies and execution order
    - Determining first steps, next steps, and completion status

    Attributes:
        workflows: Dictionary mapping workflow names to configurations
        domains: List of domain configuration mappings
        dependency_graphs: Pre-built dependency graphs for each workflow
    """

    def __init__(
        self,
        workflows: Dict[str, WorkflowConfig],
        domains: List[DomainConfig]
    ):
        """Initialize workflow resolver.

        Args:
            workflows: Dictionary of workflow name to WorkflowConfig
            domains: List of domain configurations
        """
        self.workflows = workflows
        self.domains = domains
        self.dependency_graphs = self._build_dependency_graphs()

        logger.info(
            f"✅ WorkflowResolver initialized: {len(workflows)} workflows, "
            f"{len(domains)} domains"
        )

    def match_domain_to_workflow(self, url: str) -> str:
        """Match URL domain to workflow name based on domain configuration.

        Implements three-tier matching strategy:
        1. Exact domain match (e.g., "arachne.dainst.org")
        2. Wildcard domain match (e.g., "*.dainst.org")
        3. Default workflow fallback

        Args:
            url: URL to match

        Returns:
            Workflow name

        Raises:
            ValueError: If URL is invalid or no workflow found
        """
        # Validate URL
        if not url or not isinstance(url, str) or not url.strip():
            raise ValueError("Invalid URL: URL cannot be empty or None")

        # Delegate matching to the shared resolution logic
        # (exact → wildcard → default), translating ConfigurationError to the
        # ValueError contract expected by callers.
        try:
            domain_config = self.resolve_domain_for_url(url)
        except ConfigurationError as e:
            logger.error(f"❌ No workflow found for URL '{url}': {e}")
            raise ValueError(f"No workflow configured for URL '{url}': {e}") from e

        logger.info(f"✅ Domain matched: {url} → {domain_config.workflow}")
        return domain_config.workflow

    def get_workflow(self, workflow_name: str) -> WorkflowConfig:
        """Get workflow definition by name.

        Args:
            workflow_name: Workflow name

        Returns:
            WorkflowConfig

        Raises:
            WorkflowNotFoundError: If workflow not found
        """
        if workflow_name not in self.workflows:
            available = list(self.workflows.keys())
            logger.error(
                f"Workflow '{workflow_name}' not found. Available: {available}"
            )
            raise WorkflowNotFoundError(workflow_name, available)

        return self.workflows[workflow_name]

    def get_first_step(self, workflow_name: str) -> WorkflowStepConfig:
        """Get first step (step with no dependencies).

        Args:
            workflow_name: Workflow name

        Returns:
            WorkflowStepConfig for first step

        Raises:
            ValueError: If no first step found
            WorkflowNotFoundError: If workflow not found
        """
        workflow = self.get_workflow(workflow_name)

        # Find step with no dependencies
        for step in workflow.steps:
            if not step.depends_on:
                return step

        # If all steps have dependencies, use topological sort
        execution_layers = self.resolve_dependencies(workflow.steps)
        if execution_layers and execution_layers[0]:
            return execution_layers[0][0]

        raise ValueError(f"No first step found in workflow '{workflow_name}'")

    def get_next_step(
        self,
        workflow: WorkflowConfig,
        completed_steps: Set[str]
    ) -> Optional[WorkflowStepConfig]:
        """Get next step to execute based on completed steps and dependencies.

        Args:
            workflow: Workflow configuration
            completed_steps: Set of completed step names

        Returns:
            WorkflowStepConfig for next step, or None if no next step
        """
        # Find next step whose dependencies are all completed
        for step in workflow.steps:
            # Skip if already completed
            if step.name in completed_steps:
                continue

            # Check if dependencies are met
            if not step.depends_on or all(dep in completed_steps for dep in step.depends_on):
                return step

        return None

    def is_workflow_complete(
        self,
        workflow: WorkflowConfig,
        completed_steps: Set[str]
    ) -> bool:
        """Check if all workflow steps are completed.

        Args:
            workflow: Workflow configuration
            completed_steps: Set of completed step names

        Returns:
            True if all steps completed, False otherwise
        """
        total_steps = len(workflow.steps)
        completed_count = len(completed_steps)

        return completed_count == total_steps

    def resolve_dependencies(
        self,
        steps: List[WorkflowStepConfig]
    ) -> List[List[WorkflowStepConfig]]:
        """Resolve step dependencies using topological sort (Kahn's algorithm).

        Args:
            steps: List of workflow steps

        Returns:
            List of execution layers (parallel execution possible within layer)

        Raises:
            CircularDependencyError: If circular dependencies detected
        """
        if not steps:
            return []

        # Build step lookup map
        step_map = {step.name: step for step in steps}

        # Build dependency graph and calculate in-degrees
        in_degree: Dict[str, int] = {}
        dependencies: Dict[str, List[str]] = defaultdict(list)

        for step in steps:
            if step.name not in in_degree:
                in_degree[step.name] = 0

            if step.depends_on:
                # depends_on is a List[str], iterate over it
                for dep in step.depends_on:
                    in_degree[step.name] = in_degree.get(step.name, 0) + 1
                    dependencies[dep].append(step.name)
            else:
                in_degree[step.name] = 0

        # Kahn's algorithm
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        execution_layers: List[List[WorkflowStepConfig]] = []
        processed_count = 0

        while queue:
            current_layer: List[WorkflowStepConfig] = []
            layer_size = len(queue)

            for _ in range(layer_size):
                step_name = queue.popleft()
                current_layer.append(step_map[step_name])
                processed_count += 1

                for dependent_name in dependencies[step_name]:
                    in_degree[dependent_name] -= 1
                    if in_degree[dependent_name] == 0:
                        queue.append(dependent_name)

            execution_layers.append(current_layer)

        # Check for circular dependencies
        if processed_count != len(steps):
            unprocessed = [step.name for step in steps if in_degree[step.name] > 0]
            logger.error(f"Circular dependency detected: {unprocessed}")
            raise CircularDependencyError(
                f"Circular dependency detected in workflow steps: {unprocessed}",
                unprocessed
            )

        logger.debug(
            f"Resolved {len(steps)} steps into {len(execution_layers)} execution layers"
        )
        return execution_layers

    def _build_dependency_graphs(self) -> Dict[str, Dict[str, Set[str]]]:
        """Build dependency graphs for all workflows.

        Returns:
            Dict mapping workflow names to their dependency graphs
        """
        graphs = {}
        for workflow_name, workflow in self.workflows.items():
            graph: Dict[str, Set[str]] = defaultdict(set)

            for step in workflow.steps:
                if step.depends_on:
                    # depends_on is a List[str], iterate over it
                    for dep in step.depends_on:
                        graph[dep].add(step.name)

            graphs[workflow_name] = dict(graph)

        return graphs
