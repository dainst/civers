"""Configuration models for CiVers Orchestrator using Pydantic v2."""

from typing import Annotated, Any, Dict, List, Optional

from civers_common import (
    BaseAppConfig,
    BaseDomainConfig,
    ConfigurationError,
    DomainResolutionMixin,
)
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

# Type alias for non-empty strings - replaces many redundant validators
NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class MetadataConfig(BaseModel):
    """Metadata extraction settings."""
    
    web_interface_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for downloading archived HTML"
    )



class AppConfig(BaseAppConfig):
    """Application configuration (extends civers_common BaseAppConfig).

    Inherits ``version``, ``environment`` (and an unused ``transport`` placeholder)
    from the shared base. ORCH's transport lives at the root ``ConfigDataModel``.
    """

    name: str = Field(default="civers_orchestrator", description="Application name")
    metadata: MetadataConfig = Field(default_factory=MetadataConfig, description="Metadata settings")


class KafkaConsumerConfig(BaseModel):
    """Kafka consumer configuration."""

    group_id: str = Field(description="Consumer group ID")
    auto_offset_reset: str = Field(default="earliest", description="Auto offset reset policy")


class KafkaProducerConfig(BaseModel):
    """Kafka producer configuration."""

    acks: str = Field(default="all", description="Acknowledgment policy")
    retries: int = Field(default=3, description="Number of retries")


class KafkaTopicsConfig(BaseModel):
    """Kafka topics configuration."""

    orchestrator_requests: str = Field(description="Topic for orchestrator requests")
    orchestrator_status: str = Field(description="Topic for orchestrator status updates")
    orchestrator_completed: str = Field(description="Topic for completed workflows")
    orchestrator_failed: str = Field(description="Topic for failed workflows")


class KafkaComponentMapping(BaseModel):
    """Mapping for a single component to Kafka topics and event models.

    This configuration maps transport-agnostic component identifiers to
    Kafka-specific topics and event model class names.

    Example:
        archive_generator:
          request_topic: "archive.requests"
          response_topics:
            success: "archive.completed"
            failure: "archive.failed"
          event_models:
            request: "ArchiveRequestEvent"
            success: "ArchiveCompletedEvent"
            failure: "ArchiveFailedEvent"
    """

    request_topic: NonEmptyStr = Field(description="Kafka topic for component requests")
    response_topics: Dict[str, str] = Field(
        description="Response topics (success, failure)"
    )
    event_models: Dict[str, str] = Field(
        description="Event model class names (request, success, failure)"
    )
    step_name: NonEmptyStr = Field(description="Workflow step name this component implements")


    @field_validator("response_topics")
    @classmethod
    def validate_response_topics(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate response topics has success and failure keys."""
        required_keys = {"success", "failure"}
        missing_keys = required_keys - set(v.keys())
        if missing_keys:
            raise ValueError(
                f"response_topics must include keys: {missing_keys}"
            )
        for key, value in v.items():
            if not value or not value.strip():
                raise ValueError(f"response_topics.{key} cannot be empty")
        return v

    @field_validator("event_models")
    @classmethod
    def validate_event_models(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate event models has request, success, failure keys."""
        required_keys = {"request", "success", "failure"}
        missing_keys = required_keys - set(v.keys())
        if missing_keys:
            raise ValueError(
                f"event_models must include keys: {missing_keys}"
            )
        for key, value in v.items():
            if not value or not value.strip():
                raise ValueError(f"event_models.{key} cannot be empty")
        return v


class KafkaConfig(BaseModel):
    """Kafka transport configuration."""

    bootstrap_servers: str = Field(description="Kafka bootstrap servers")
    consumer: KafkaConsumerConfig = Field(description="Consumer configuration")
    producer: KafkaProducerConfig = Field(description="Producer configuration")
    topics: KafkaTopicsConfig = Field(description="Topics configuration")
    component_mappings: Dict[str, KafkaComponentMapping] = Field(
        default_factory=dict,
        description="Component-to-Kafka mappings (component_id -> topics/events)"
    )


class TransportConfig(BaseModel):
    """Transport layer configuration."""

    enabled: List[str] = Field(default=["kafka"], description="Enabled transport mechanisms")
    kafka: KafkaConfig = Field(description="Kafka configuration")


class DataTransformerConfig(BaseModel):
    """Configuration for transforming data between workflow steps.

    Data transformers enable passing data from one step to another step in a
    configurable way, eliminating the need for hardcoded step-specific logic
    in the orchestrator.

    Example:
        # Transform snapshot_id from archive_generation step to document_url for metadata_extraction
        DataTransformerConfig(
            source_step="archive_generation",
            source_field="snapshot_id",
            target_field="document_url",
            transformer="build_web_interface_url",
            required=True,
            transformer_config={
                "base_url_config_path": "app.metadata.web_interface_url",
                "default_base_url": "http://localhost:8000",
                "url_template": "{base_url}/api/artifacts/serve?snapshot_id={value}&type=dom-snapshot.html"
            }
        )
    """

    source_step: NonEmptyStr = Field(description="Name of step providing the data")
    source_field: NonEmptyStr = Field(description="Field name in source step results")
    target_field: NonEmptyStr = Field(description="Field name in target step input")
    transformer: NonEmptyStr = Field(description="Transformer function name")
    transformer_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration for transformer function"
    )
    required: bool = Field(
        default=True,
        description="Whether this field is required (fails if missing)"
    )


class WorkflowStepConfig(BaseModel):
    """Transport-agnostic configuration for a single workflow step.

    This model contains ONLY transport-agnostic fields. Transport-specific
    concepts (topics, event models) are configured separately in transport
    configuration (e.g., kafka.yaml component_mappings).

    - component: Identifies which service to invoke
    - input_schema: Data contract name for input
    - output_schemas: Data contract names for success/failure outcomes
    - depends_on: List of step names this step depends on

    Example:
        step = WorkflowStepConfig(
            name="archive_generation",
            component="archive_generator",
            input_schema="ArchiveRequest",
            output_schemas={"success": "ArchiveCompleted", "failure": "ArchiveFailed"},
            depends_on=[],
            timeout_seconds=300
        )
    """

    name: NonEmptyStr = Field(description="Step name")
    component: NonEmptyStr = Field(description="Component identifier")
    input_schema: NonEmptyStr = Field(description="Input data schema name")
    output_schemas: Dict[str, str] = Field(
        description="Output schemas for success/failure outcomes"
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="List of step names this step depends on"
    )
    timeout_seconds: int = Field(default=300, gt=0, description="Timeout in seconds")
    input_transformers: List["DataTransformerConfig"] = Field(
        default_factory=list,
        description="Data transformers for constructing input from previous steps"
    )


    @field_validator("output_schemas")
    @classmethod
    def validate_output_schemas(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate output schemas has success and failure keys."""
        required_keys = {"success", "failure"}
        missing_keys = required_keys - set(v.keys())
        if missing_keys:
            raise ValueError(
                f"output_schemas must include keys: {missing_keys}"
            )
        for key, value in v.items():
            if not value or not value.strip():
                raise ValueError(f"output_schemas.{key} cannot be empty")
        return v




class WorkflowConfig(BaseModel):
    """Configuration for a complete workflow."""

    name: NonEmptyStr = Field(description="Workflow name")
    description: str = Field(description="Workflow description")
    steps: List[WorkflowStepConfig] = Field(description="Workflow steps")

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: List[WorkflowStepConfig]) -> List[WorkflowStepConfig]:
        """Validate workflow steps have valid dependencies."""
        if not v:
            raise ValueError("Workflow must have at least one step")

        # Check for duplicate step names
        step_names_list = [step.name for step in v]
        step_names_set = set(step_names_list)
        if len(step_names_list) != len(step_names_set):
            raise ValueError("Workflow steps must have unique names")

        # Check dependencies reference existing steps
        for step in v:
            if step.depends_on:
                for dep in step.depends_on:
                    if dep not in step_names_set:
                        raise ValueError(
                            f"Step '{step.name}' depends on non-existent step '{dep}'"
                        )

        # Check for circular dependencies
        def has_circular_dependency(start_step: str, visited: set) -> bool:
            if start_step in visited:
                return True
            visited.add(start_step)

            # Find the step object
            step_obj = next((s for s in v if s.name == start_step), None)
            if step_obj and step_obj.depends_on:
                for dep in step_obj.depends_on:
                    if has_circular_dependency(dep, visited.copy()):
                        return True
            return False

        for step in v:
            if has_circular_dependency(step.name, set()):
                raise ValueError(
                    f"Circular dependency detected involving step '{step.name}'"
                )

        return v


class DomainConfig(BaseDomainConfig):
    """Domain-to-workflow mapping (extends civers_common BaseDomainConfig).

    Inherits ``name`` (with validation), ``enabled``, ``description`` and
    ``webpage_types`` from the shared base; adds the ORCH-specific ``workflow``.
    """

    workflow: NonEmptyStr = Field(description="Workflow name to use for this domain")


class ConfigDataModel(DomainResolutionMixin, BaseModel):
    """Root configuration model.

    Uses ``civers_common.DomainResolutionMixin`` for the shared
    exact → wildcard → default domain resolution.
    """

    app: AppConfig = Field(description="Application configuration")
    transport: TransportConfig = Field(description="Transport configuration")
    domains: List[DomainConfig] = Field(description="Domain-to-workflow mappings")
    workflows: List[WorkflowConfig] = Field(description="Workflow definitions")

    @field_validator("workflows")
    @classmethod
    def validate_workflows(cls, v: List[WorkflowConfig]) -> List[WorkflowConfig]:
        """Validate workflow names are unique."""
        workflow_names = [w.name for w in v]
        if len(workflow_names) != len(set(workflow_names)):
            raise ValueError("Workflow names must be unique")
        return v

    @model_validator(mode="after")
    def validate_domain_workflow_references(self) -> "ConfigDataModel":
        """Validate domain configurations reference existing workflows."""
        workflow_names = {w.name for w in self.workflows}
        for domain in self.domains:
            if domain.workflow not in workflow_names:
                raise ValueError(
                    f"Domain '{domain.name}' references non-existent "
                    f"workflow '{domain.workflow}'"
                )
        return self

    def get_workflow_by_name(self, name: str) -> Optional[WorkflowConfig]:
        """Get workflow configuration by name."""
        for workflow in self.workflows:
            if workflow.name == name:
                return workflow
        return None

    def get_workflow_for_domain(self, domain: str) -> Optional[WorkflowConfig]:
        """Get workflow for a given domain via shared domain resolution.

        Delegates matching to ``DomainResolutionMixin.resolve_domain``
        (exact → wildcard → default). Returns ``None`` when no domain matches.
        """
        try:
            domain_config = self.resolve_domain(domain)
        except ConfigurationError:
            return None
        return self.get_workflow_by_name(domain_config.workflow)
