"""Tests for transport-agnostic workflow and orchestrator models.

Task 13: Write tests FIRST (RED), then update models (GREEN).

These tests verify that workflow models contain NO transport-specific concepts
(topics, event models), only transport-agnostic schemas and component identifiers.
"""

import pytest
from pydantic import ValidationError


class TestTransportAgnosticWorkflowStepConfig:
    """Test transport-agnostic WorkflowStepConfig model."""

    def test_valid_transport_agnostic_step_config(self):
        """Test creating valid transport-agnostic step configuration."""
        from configs.models import WorkflowStepConfig

        step = WorkflowStepConfig(
            name="archive_generation",
            component="archive_generator",
            input_schema="ArchiveRequest",
            output_schemas={
                "success": "ArchiveCompleted",
                "failure": "ArchiveFailed"
            },
            timeout_seconds=300
        )

        assert step.name == "archive_generation"
        assert step.component == "archive_generator"
        assert step.input_schema == "ArchiveRequest"
        assert step.output_schemas["success"] == "ArchiveCompleted"
        assert step.output_schemas["failure"] == "ArchiveFailed"
        assert step.timeout_seconds == 300

    def test_step_config_has_no_input_topic_field(self):
        """Test that WorkflowStepConfig has NO input_topic field."""
        from configs.models import WorkflowStepConfig

        step = WorkflowStepConfig(
            name="test",
            component="test_component",
            input_schema="TestRequest",
            output_schemas={"success": "Success", "failure": "Failed"},
            timeout_seconds=60
        )

        # Should NOT have Kafka-specific fields
        assert not hasattr(step, 'input_topic')
        assert not hasattr(step, 'input_event_model')
        assert not hasattr(step, 'output_topics')
        assert not hasattr(step, 'output_event_models')

    def test_step_config_requires_component(self):
        """Test that component is required."""
        from configs.models import WorkflowStepConfig

        with pytest.raises(ValidationError, match="component"):
            WorkflowStepConfig(
                name="test",
                input_schema="TestRequest",
                output_schemas={"success": "Success", "failure": "Failed"},
                timeout_seconds=60
            )

    def test_step_config_requires_input_schema(self):
        """Test that input_schema is required."""
        from configs.models import WorkflowStepConfig

        with pytest.raises(ValidationError, match="input_schema"):
            WorkflowStepConfig(
                name="test",
                component="test_component",
                output_schemas={"success": "Success", "failure": "Failed"},
                timeout_seconds=60
            )

    def test_step_config_requires_output_schemas(self):
        """Test that output_schemas is required."""
        from configs.models import WorkflowStepConfig

        with pytest.raises(ValidationError, match="output_schemas"):
            WorkflowStepConfig(
                name="test",
                component="test_component",
                input_schema="TestRequest",
                timeout_seconds=60
            )

    def test_step_config_with_dependencies(self):
        """Test step config with depends_on field."""
        from configs.models import WorkflowStepConfig

        step = WorkflowStepConfig(
            name="metadata_extraction",
            component="metadata_extractor",
            input_schema="MetadataRequest",
            output_schemas={"success": "MetadataCompleted", "failure": "MetadataFailed"},
            depends_on=["archive_generation"],
            timeout_seconds=60
        )

        assert step.depends_on == ["archive_generation"]

    def test_step_config_depends_on_defaults_to_empty_list(self):
        """Test that depends_on defaults to empty list."""
        from configs.models import WorkflowStepConfig

        step = WorkflowStepConfig(
            name="test",
            component="test_component",
            input_schema="TestRequest",
            output_schemas={"success": "Success", "failure": "Failed"},
            timeout_seconds=60
        )

        assert step.depends_on == []


class TestTransportAgnosticStepInstruction:
    """Test transport-agnostic StepInstruction model."""

    def test_valid_transport_agnostic_instruction(self):
        """Test creating valid transport-agnostic step instruction."""
        from configs.models import WorkflowStepConfig
        from models.orchestrator_models import StepInstruction

        step_config = WorkflowStepConfig(
            name="archive_generation",
            component="archive_generator",
            input_schema="ArchiveRequest",
            output_schemas={"success": "ArchiveCompleted", "failure": "ArchiveFailed"},
            timeout_seconds=300
        )

        instruction = StepInstruction(
            step_config=step_config,
            request_id="req-123",
            url="https://example.com",
            component="archive_generator",
            input_schema="ArchiveRequest",
            input_data={"priority": 1}
        )

        assert instruction.request_id == "req-123"
        assert instruction.url == "https://example.com"
        assert instruction.component == "archive_generator"
        assert instruction.input_schema == "ArchiveRequest"
        assert instruction.input_data["priority"] == 1

    def test_instruction_has_no_kafka_fields(self):
        """Test that StepInstruction has NO Kafka-specific fields."""
        from configs.models import WorkflowStepConfig
        from models.orchestrator_models import StepInstruction

        step_config = WorkflowStepConfig(
            name="test",
            component="test_component",
            input_schema="TestRequest",
            output_schemas={"success": "Success", "failure": "Failed"},
            timeout_seconds=60
        )

        instruction = StepInstruction(
            step_config=step_config,
            request_id="req-123",
            url="https://example.com",
            component="test_component",
            input_schema="TestRequest",
            input_data={}
        )

        # Should NOT have Kafka-specific fields
        assert not hasattr(instruction, 'input_topic')
        assert not hasattr(instruction, 'input_event_model')

    def test_instruction_with_metadata(self):
        """Test instruction with optional metadata."""
        from configs.models import WorkflowStepConfig
        from models.orchestrator_models import StepInstruction

        step_config = WorkflowStepConfig(
            name="test",
            component="test_component",
            input_schema="TestRequest",
            output_schemas={"success": "Success", "failure": "Failed"},
            timeout_seconds=60
        )

        instruction = StepInstruction(
            step_config=step_config,
            request_id="req-123",
            url="https://example.com",
            component="test_component",
            input_schema="TestRequest",
            input_data={},
            metadata={"callback_url": "https://callback.example.com"}
        )

        assert instruction.metadata["callback_url"] == "https://callback.example.com"

    def test_instruction_component_matches_step_config(self):
        """Test that instruction component matches step config component."""
        from configs.models import WorkflowStepConfig
        from models.orchestrator_models import StepInstruction

        step_config = WorkflowStepConfig(
            name="archive_generation",
            component="archive_generator",
            input_schema="ArchiveRequest",
            output_schemas={"success": "ArchiveCompleted", "failure": "ArchiveFailed"},
            timeout_seconds=300
        )

        instruction = StepInstruction(
            step_config=step_config,
            request_id="req-123",
            url="https://example.com",
            component="archive_generator",  # Must match step_config.component
            input_schema="ArchiveRequest",
            input_data={}
        )

        assert instruction.component == step_config.component
        assert instruction.input_schema == step_config.input_schema


class TestWorkflowConfigLoadsTransportAgnostic:
    """Test that workflow configuration loads with transport-agnostic format."""

    def test_load_transport_agnostic_workflow_config(self):
        """Test loading workflow config with no Kafka fields."""
        from configs.loaders import YamlFileConfigLoader

        config = YamlFileConfigLoader().load()

        # Verify workflows loaded
        assert len(config.workflows) > 0

        # Check first workflow's first step
        first_workflow = config.workflows[0]
        first_step = first_workflow.steps[0]

        # Should have transport-agnostic fields
        assert hasattr(first_step, 'component')
        assert hasattr(first_step, 'input_schema')
        assert hasattr(first_step, 'output_schemas')

        # Should NOT have Kafka-specific fields
        assert not hasattr(first_step, 'input_topic')
        assert not hasattr(first_step, 'input_event_model')
        assert not hasattr(first_step, 'output_topics')
        assert not hasattr(first_step, 'output_event_models')

    def test_workflow_steps_use_schema_names_not_event_models(self):
        """Test that workflow steps reference schemas, not event models."""
        from configs.loaders import YamlFileConfigLoader

        config = YamlFileConfigLoader().load()

        for workflow in config.workflows:
            for step in workflow.steps:
                # Schema names should be simpler (no "Event" suffix)
                assert step.input_schema
                assert not step.input_schema.endswith("Event")

                # Output schemas should have success/failure
                assert "success" in step.output_schemas
                assert "failure" in step.output_schemas

    def test_workflow_archive_generator_step_format(self):
        """Test archive_generator step has correct transport-agnostic format."""
        from configs.loaders import YamlFileConfigLoader

        config = YamlFileConfigLoader().load()

        # Find archive_generator step in any workflow
        archive_step = None
        for workflow in config.workflows:
            for step in workflow.steps:
                if step.component == "archive_generator":
                    archive_step = step
                    break
            if archive_step:
                break

        assert archive_step is not None
        assert archive_step.name == "archive_generation"
        assert archive_step.component == "archive_generator"
        assert archive_step.input_schema == "ArchiveRequest"
        assert archive_step.output_schemas["success"] == "ArchiveCompleted"
        assert archive_step.output_schemas["failure"] == "ArchiveFailed"

    def test_workflow_metadata_extractor_step_format(self):
        """Test metadata_extractor step has correct transport-agnostic format."""
        from configs.loaders import YamlFileConfigLoader

        config = YamlFileConfigLoader().load()

        # Find metadata_extractor step
        metadata_step = None
        for workflow in config.workflows:
            for step in workflow.steps:
                if step.component == "metadata_extractor":
                    metadata_step = step
                    break
            if metadata_step:
                break

        assert metadata_step is not None
        assert metadata_step.component == "metadata_extractor"
        assert metadata_step.input_schema == "MetadataRequest"
        assert metadata_step.output_schemas["success"] == "MetadataCompleted"
        assert metadata_step.output_schemas["failure"] == "MetadataFailed"
