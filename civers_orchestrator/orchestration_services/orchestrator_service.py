"""Pure Business Logic Orchestrator Service for CiVers Orchestrator.

This service provides pure business logic orchestration using a modular architecture.
It coordinates between specialized components for state management, workflow resolution,
step execution, and timeout monitoring.

Key Principles:
- NO Kafka imports or knowledge
- NO EventPublisher dependency
- Returns instructions (StepInstruction, WorkflowTransition)
- Transport layer executes instructions
- Modular architecture with single-responsibility components
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from configs.logging_config import get_logger
from configs.models import ConfigDataModel, DomainConfig, WorkflowConfig
from models.orchestrator_models import StepInstruction, WorkflowTransition, WorkflowStatus
from models.workflow_models import WorkflowInstance, WorkflowStepInstance, WorkflowStepStatus
from orchestration_services.orchestrator_service_interface import OrchestratorServiceInterface
from orchestration_services.step_executor import StepExecutor
from orchestration_services.timeout_monitor import TimeoutMonitor
from orchestration_services.workflow_resolver import WorkflowResolver
from orchestration_services.workflow_state_store import WorkflowStateStore

logger = get_logger(__name__)


class OrchestratorService(OrchestratorServiceInterface):
    """
    Pure business logic orchestrator with modular architecture.

    This class acts as a facade, coordinating between specialized components:
    - WorkflowStateStore: Thread-safe state management
    - WorkflowResolver: Domain matching and dependency resolution
    - StepExecutor: Step instruction creation with transformers
    - TimeoutMonitor: Timeout detection and handling

    Responsibilities:
    - Coordinate workflow execution across components
    - Provide unified public API for workflow operations
    - Maintain backward compatibility with existing interface

    What it DOES NOT do:
    - NO Kafka message handling
    - NO event publishing
    - NO transport operations
    - Returns instructions instead of publishing events
    """

    def __init__(self, config: ConfigDataModel):
        """
        Initialize orchestrator with configuration.

        Creates and initializes all specialized components needed for
        workflow orchestration.

        Args:
            config: Complete application configuration
        """
        self.config = config

        # Load configurations
        domains: List[DomainConfig] = config.domains
        workflows_dict: Dict[str, WorkflowConfig] = {
            wf.name: wf for wf in config.workflows
        }

        # Initialize specialized components
        self.state_store = WorkflowStateStore(max_stored_workflows=10000)
        self.resolver = WorkflowResolver(workflows_dict, domains)
        self.executor = StepExecutor(config)
        self.timeout_monitor = TimeoutMonitor(self.state_store, workflows_dict)

        # Store workflows for easy access
        self.workflows = workflows_dict

        logger.info(
            f"✅ OrchestratorService initialized: {len(workflows_dict)} workflows, "
            f"{len(domains)} domains"
        )

    # === PUBLIC API (returns instructions) ===

    def start_workflow(
        self,
        request_id: str,
        url: str,
        workflow_name: Optional[str] = None,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> StepInstruction:
        """
        Start a new workflow execution.

        Args:
            request_id: Unique request identifier
            url: URL to process
            workflow_name: Optional explicit workflow name (if None, matches by domain)
            callback_url: Optional callback URL for notifications
            metadata: Optional metadata to pass through workflow

        Returns:
            StepInstruction: Instruction for executing the first step

        Raises:
            WorkflowNotFoundError: If workflow doesn't exist
            CircularDependencyError: If workflow has circular dependencies
        """
        logger.info(f"🚀 Starting workflow for request {request_id}: {url}")

        # 1. Determine workflow to use
        if workflow_name:
            logger.info(f"Using explicit workflow: {workflow_name}")
        else:
            workflow_name = self.resolver.match_domain_to_workflow(url)
            logger.info(f"Matched domain to workflow: {workflow_name}")

        # 2. Validate workflow exists
        workflow = self.resolver.get_workflow(workflow_name)

        # 3. Create workflow instance
        workflow_instance = WorkflowInstance(
            request_id=request_id,
            workflow_name=workflow_name,
            url=url,
            status=WorkflowStepStatus.IN_PROGRESS,
            steps=[WorkflowStepInstance(name=step.name) for step in workflow.steps],
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            callback_url=callback_url,
            metadata=metadata or {},
            start_time=datetime.now(timezone.utc),
            completed_steps=set(),
            failed_steps=set(),
            step_results={}
        )

        # 4. Save state
        self.state_store.store_workflow(request_id, workflow_instance)

        # 5. Get first step
        first_step = self.resolver.get_first_step(workflow_name)
        workflow_instance.current_step = first_step.name

        logger.info(
            f"✅ Workflow '{workflow_name}' initialized for {request_id}, "
            f"first step: {first_step.name}"
        )

        # 6. Return instruction for first step
        return self.executor.create_step_instruction(workflow_instance, first_step)

    def step_completed(
        self,
        request_id: str,
        step_name: str,
        result_data: Optional[Dict] = None
    ) -> WorkflowTransition:
        """
        Handle step completion and determine next action.

        Args:
            request_id: Request identifier
            step_name: Name of completed step
            result_data: Optional result data from step

        Returns:
            WorkflowTransition: What to do next (execute_step, workflow_complete)

        Raises:
            ValueError: If request_id not found or step is invalid
        """
        logger.info(f"✅ Step '{step_name}' completed for request {request_id}")

        # 1. Get workflow instance
        workflow_instance = self.state_store.get_workflow(request_id)
        if not workflow_instance:
            raise ValueError(f"Unknown request_id: {request_id}")

        # 2. Mark step as completed
        workflow_instance.mark_step_completed(step_name, result_data)

        # 3. Get workflow config
        workflow = self.resolver.get_workflow(workflow_instance.workflow_name)

        # 4. Check if workflow is complete
        if self.resolver.is_workflow_complete(workflow, workflow_instance.completed_steps):
            workflow_instance.mark_workflow_complete()
            self.state_store.update_workflow(request_id, workflow_instance)
            logger.info(f"✅ Workflow completed for request {request_id}")

            return WorkflowTransition(
                action="workflow_complete",
                request_id=request_id,
                workflow_instance=workflow_instance
            )

        # 5. Get next step(s) based on dependencies
        next_step = self.resolver.get_next_step(workflow, workflow_instance.completed_steps)

        if next_step:
            workflow_instance.current_step = next_step.name
            self.state_store.update_workflow(request_id, workflow_instance)
            instruction = self.executor.create_step_instruction(workflow_instance, next_step)

            logger.info(
                f"➡️  Next step for request {request_id}: {next_step.name}"
            )

            return WorkflowTransition(
                action="execute_step",
                request_id=request_id,
                step_instruction=instruction
            )
        else:
            # No next step but workflow not complete - shouldn't happen
            raise ValueError(
                f"No next step found but workflow not complete for {request_id}"
            )

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

        Raises:
            ValueError: If request_id not found
        """
        logger.error(f"❌ Step '{step_name}' failed for request {request_id}: {error_message}")

        # 1. Get workflow instance
        workflow_instance = self.state_store.get_workflow(request_id)
        if not workflow_instance:
            raise ValueError(f"Unknown request_id: {request_id}")

        # 2. Mark step as failed
        workflow_instance.mark_step_failed(step_name, error_message)
        self.state_store.update_workflow(request_id, workflow_instance)

        logger.error(
            f"❌ Workflow failed for request {request_id} at step '{step_name}'"
        )

        # 3. Return failure transition
        return WorkflowTransition(
            action="workflow_failed",
            request_id=request_id,
            workflow_instance=workflow_instance,
            error_message=error_message,
            failed_step=step_name
        )

    def get_workflow_state(self, request_id: str) -> Optional[WorkflowInstance]:
        """
        Get current workflow state for a request.

        Args:
            request_id: Request identifier

        Returns:
            WorkflowInstance if found, None otherwise
        """
        return self.state_store.get_workflow(request_id)

    def get_workflow_status(self, request_id: str) -> Optional[WorkflowStatus]:
        """
        Get workflow status for monitoring/queries.

        Args:
            request_id: Request identifier

        Returns:
            WorkflowStatus if workflow exists, None otherwise
        """
        workflow_instance = self.state_store.get_workflow(request_id)
        if not workflow_instance:
            return None

        workflow = self.resolver.get_workflow(workflow_instance.workflow_name)

        return WorkflowStatus(
            request_id=request_id,
            workflow_name=workflow_instance.workflow_name,
            url=workflow_instance.url,
            current_step=workflow_instance.current_step,
            completed_steps=workflow_instance.completed_steps,
            total_steps=len(workflow.steps),
            status=workflow_instance.status.value,
            error_message=workflow_instance.error_message,
            failed_step=workflow_instance.failed_at_step
        )

    # === MEMORY MANAGEMENT METHODS ===

    def cleanup_completed_workflows(self, max_age_seconds: int = 3600) -> int:
        """
        Remove completed/failed workflows older than specified age.

        Args:
            max_age_seconds: Remove workflows completed this long ago (default: 1 hour)

        Returns:
            Number of workflows removed
        """
        return self.state_store.cleanup_completed_workflows(max_age_seconds)

    # === TIMEOUT HANDLING METHODS ===

    def check_step_timeout(self, request_id: str) -> Optional[WorkflowTransition]:
        """
        Check if current step has exceeded its timeout.

        Args:
            request_id: Request identifier

        Returns:
            WorkflowTransition if timeout occurred, None otherwise
        """
        timeout_info = self.timeout_monitor.check_step_timeout(request_id)
        if timeout_info:
            # Convert timeout info to WorkflowTransition by calling step_failed
            return self.step_failed(
                request_id,
                timeout_info["step_name"],
                timeout_info["error_message"]
            )

        return None

    def check_all_timeouts(self) -> List[WorkflowTransition]:
        """
        Check all active workflows for timeouts.

        Returns:
            List of WorkflowTransitions for timed-out workflows
        """
        transitions = []
        timeout_infos = self.timeout_monitor.check_all_timeouts()

        for timeout_info in timeout_infos:
            transition = self.step_failed(
                timeout_info["request_id"],
                timeout_info["step_name"],
                timeout_info["error_message"]
            )
            transitions.append(transition)

        return transitions
