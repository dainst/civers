"""Step execution and instruction creation.

This module handles the creation of step instructions using data transformers
to pass data between workflow steps. This replaces hardcoded step-specific logic
with a flexible, configuration-driven approach.
"""


from configs.logging_config import get_logger
from configs.models import ConfigDataModel, WorkflowStepConfig
from models.orchestrator_models import StepInstruction
from models.workflow_models import WorkflowInstance
from orchestration_services.data_transformers import apply_transformer

logger = get_logger(__name__)


class StepExecutor:
    """Creates step instructions with data transformer support.

    This class is responsible for creating StepInstruction objects that
    the transport layer uses to execute workflow steps. It applies data
    transformers to construct step input from previous step results.

    Attributes:
        config: Application configuration (used for transformer context)
    """

    def __init__(self, config: ConfigDataModel):
        """Initialize step executor.

        Args:
            config: Application configuration
        """
        self.config = config
        logger.info("✅ StepExecutor initialized")

    def create_step_instruction(
        self,
        workflow_instance: WorkflowInstance,
        step: WorkflowStepConfig
    ) -> StepInstruction:
        """Create instruction for executing a step.

        Uses data transformers to construct input data from previous step results,
        eliminating hardcoded step-specific logic. The orchestrator remains generic
        and knows nothing about specific step implementations.

        Args:
            workflow_instance: Current workflow instance with step results
            step: Step configuration to execute

        Returns:
            StepInstruction for transport layer to execute

        Raises:
            ValueError: If required transformer field is missing
        """
        # Build base input data
        input_data = {
            "callback_url": workflow_instance.callback_url,
            "priority": workflow_instance.metadata.get("priority", 1),
        }

        # Apply data transformers (replaces hardcoded logic)
        if step.input_transformers:
            context = {"orchestrator_config": self.config}

            for transformer_config in step.input_transformers:
                # Get value from source step results
                source_results = workflow_instance.step_results.get(
                    transformer_config.source_step,
                    {}
                )
                source_value = source_results.get(transformer_config.source_field)

                # Check if required
                if transformer_config.required and not source_value:
                    available_fields = list(source_results.keys())
                    logger.error(
                        f"❌ Required field '{transformer_config.source_field}' missing from "
                        f"step '{transformer_config.source_step}' results. "
                        f"Available fields: {available_fields}"
                    )
                    raise ValueError(
                        f"Required field '{transformer_config.source_field}' missing from "
                        f"step '{transformer_config.source_step}' results. "
                        f"Available fields: {available_fields}"
                    )

                if source_value:
                    # Apply transformer
                    try:
                        transformed_value = apply_transformer(
                            transformer_config.transformer,
                            source_value,
                            transformer_config.transformer_config,
                            context
                        )

                        input_data[transformer_config.target_field] = transformed_value

                        logger.info(
                            f"   ✅ Transformed {transformer_config.source_step}.{transformer_config.source_field} → "
                            f"{transformer_config.target_field}: {transformed_value}"
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ Failed to transform data for step '{step.name}': {e}"
                        )
                        if transformer_config.required:
                            raise

        return StepInstruction(
            step_config=step,
            request_id=workflow_instance.request_id,
            url=workflow_instance.url,
            component=step.component,
            input_schema=step.input_schema,
            input_data=input_data,
            workflow_instance=workflow_instance,
            metadata=workflow_instance.metadata
        )
