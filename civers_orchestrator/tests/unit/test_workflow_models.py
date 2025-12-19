"""Unit tests for workflow state models."""

import pytest
from pydantic import ValidationError


class TestWorkflowStepStatus:
    """Tests for WorkflowStepStatus enum."""

    def test_workflow_step_status_values(self):
        """Test that WorkflowStepStatus has all required values."""
        from models.workflow_models import WorkflowStepStatus

        assert WorkflowStepStatus.PENDING == "pending"
        assert WorkflowStepStatus.IN_PROGRESS == "in_progress"
        assert WorkflowStepStatus.COMPLETED == "completed"
        assert WorkflowStepStatus.FAILED == "failed"
        assert WorkflowStepStatus.TIMEOUT == "timeout"

    def test_workflow_step_status_enum_membership(self):
        """Test enum membership."""
        from models.workflow_models import WorkflowStepStatus

        assert "pending" in [s.value for s in WorkflowStepStatus]
        assert "in_progress" in [s.value for s in WorkflowStepStatus]
        assert "completed" in [s.value for s in WorkflowStepStatus]
        assert "failed" in [s.value for s in WorkflowStepStatus]
        assert "timeout" in [s.value for s in WorkflowStepStatus]


class TestWorkflowStepInstance:
    """Tests for WorkflowStepInstance model."""

    def test_valid_step_instance(self):
        """Test creating a valid workflow step instance."""
        from models.workflow_models import WorkflowStepInstance, WorkflowStepStatus

        step = WorkflowStepInstance(name="archive_generation")

        assert step.name == "archive_generation"
        assert step.status == WorkflowStepStatus.PENDING
        assert step.started_at is None
        assert step.completed_at is None
        assert step.error_message is None

    def test_step_instance_with_status(self):
        """Test step instance with different status."""
        from models.workflow_models import WorkflowStepInstance, WorkflowStepStatus

        step = WorkflowStepInstance(
            name="metadata_extraction",
            status=WorkflowStepStatus.IN_PROGRESS,
            started_at="2024-01-15T10:00:00Z"
        )

        assert step.status == WorkflowStepStatus.IN_PROGRESS
        assert step.started_at == "2024-01-15T10:00:00Z"

    def test_step_instance_completed(self):
        """Test completed step instance."""
        from models.workflow_models import WorkflowStepInstance, WorkflowStepStatus

        step = WorkflowStepInstance(
            name="doi_assignment",
            status=WorkflowStepStatus.COMPLETED,
            started_at="2024-01-15T10:00:00Z",
            completed_at="2024-01-15T10:00:30Z"
        )

        assert step.status == WorkflowStepStatus.COMPLETED
        assert step.completed_at == "2024-01-15T10:00:30Z"

    def test_step_instance_failed(self):
        """Test failed step instance with error message."""
        from models.workflow_models import WorkflowStepInstance, WorkflowStepStatus

        step = WorkflowStepInstance(
            name="archive_generation",
            status=WorkflowStepStatus.FAILED,
            started_at="2024-01-15T10:00:00Z",
            error_message="Timeout after 300 seconds"
        )

        assert step.status == WorkflowStepStatus.FAILED
        assert step.error_message == "Timeout after 300 seconds"

    def test_step_instance_json_serialization(self):
        """Test step instance JSON serialization."""
        from models.workflow_models import WorkflowStepInstance, WorkflowStepStatus
        import json

        step = WorkflowStepInstance(
            name="test_step",
            status=WorkflowStepStatus.IN_PROGRESS
        )

        json_str = step.model_dump_json()
        data = json.loads(json_str)

        assert data["name"] == "test_step"
        assert data["status"] == "in_progress"


class TestWorkflowInstance:
    """Tests for WorkflowInstance model."""

    def test_valid_workflow_instance(self):
        """Test creating a valid workflow instance."""
        from models.workflow_models import WorkflowInstance, WorkflowStepInstance, WorkflowStepStatus

        steps = [
            WorkflowStepInstance(name="archive_generation"),
            WorkflowStepInstance(name="metadata_extraction"),
            WorkflowStepInstance(name="doi_assignment")
        ]

        workflow = WorkflowInstance(
            request_id="req-123",
            workflow_name="standard_archive_workflow",
            url="https://example.com/page",
            status=WorkflowStepStatus.PENDING,
            steps=steps,
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:00:00Z"
        )

        assert workflow.request_id == "req-123"
        assert workflow.workflow_name == "standard_archive_workflow"
        assert workflow.url == "https://example.com/page"
        assert workflow.status == WorkflowStepStatus.PENDING
        assert len(workflow.steps) == 3
        assert workflow.metadata == {}

    def test_workflow_instance_with_metadata(self):
        """Test workflow instance with metadata."""
        from models.workflow_models import WorkflowInstance, WorkflowStepStatus

        workflow = WorkflowInstance(
            request_id="req-123",
            workflow_name="test_workflow",
            url="https://example.com/page",
            status=WorkflowStepStatus.IN_PROGRESS,
            steps=[],
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:00:00Z",
            metadata={"priority": 5, "source": "api"}
        )

        assert workflow.metadata["priority"] == 5
        assert workflow.metadata["source"] == "api"

    def test_workflow_instance_in_progress(self):
        """Test workflow instance in progress state."""
        from models.workflow_models import WorkflowInstance, WorkflowStepInstance, WorkflowStepStatus

        steps = [
            WorkflowStepInstance(
                name="archive_generation",
                status=WorkflowStepStatus.COMPLETED,
                started_at="2024-01-15T10:00:00Z",
                completed_at="2024-01-15T10:05:00Z"
            ),
            WorkflowStepInstance(
                name="metadata_extraction",
                status=WorkflowStepStatus.IN_PROGRESS,
                started_at="2024-01-15T10:05:01Z"
            )
        ]

        workflow = WorkflowInstance(
            request_id="req-123",
            workflow_name="test_workflow",
            url="https://example.com/page",
            status=WorkflowStepStatus.IN_PROGRESS,
            steps=steps,
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:05:01Z"
        )

        assert workflow.status == WorkflowStepStatus.IN_PROGRESS
        assert workflow.steps[0].status == WorkflowStepStatus.COMPLETED
        assert workflow.steps[1].status == WorkflowStepStatus.IN_PROGRESS

    def test_workflow_instance_completed(self):
        """Test completed workflow instance."""
        from models.workflow_models import WorkflowInstance, WorkflowStepInstance, WorkflowStepStatus

        steps = [
            WorkflowStepInstance(
                name="step1",
                status=WorkflowStepStatus.COMPLETED,
                started_at="2024-01-15T10:00:00Z",
                completed_at="2024-01-15T10:01:00Z"
            ),
            WorkflowStepInstance(
                name="step2",
                status=WorkflowStepStatus.COMPLETED,
                started_at="2024-01-15T10:01:00Z",
                completed_at="2024-01-15T10:02:00Z"
            )
        ]

        workflow = WorkflowInstance(
            request_id="req-123",
            workflow_name="test_workflow",
            url="https://example.com/page",
            status=WorkflowStepStatus.COMPLETED,
            steps=steps,
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:02:00Z"
        )

        assert workflow.status == WorkflowStepStatus.COMPLETED
        assert all(step.status == WorkflowStepStatus.COMPLETED for step in workflow.steps)

    def test_workflow_instance_failed(self):
        """Test failed workflow instance."""
        from models.workflow_models import WorkflowInstance, WorkflowStepInstance, WorkflowStepStatus

        steps = [
            WorkflowStepInstance(
                name="archive_generation",
                status=WorkflowStepStatus.FAILED,
                started_at="2024-01-15T10:00:00Z",
                error_message="Connection timeout"
            )
        ]

        workflow = WorkflowInstance(
            request_id="req-123",
            workflow_name="test_workflow",
            url="https://example.com/page",
            status=WorkflowStepStatus.FAILED,
            steps=steps,
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:00:30Z"
        )

        assert workflow.status == WorkflowStepStatus.FAILED
        assert workflow.steps[0].status == WorkflowStepStatus.FAILED
        assert workflow.steps[0].error_message == "Connection timeout"

    def test_workflow_instance_json_serialization(self):
        """Test workflow instance JSON serialization."""
        from models.workflow_models import WorkflowInstance, WorkflowStepInstance, WorkflowStepStatus
        import json

        steps = [WorkflowStepInstance(name="test_step")]

        workflow = WorkflowInstance(
            request_id="req-123",
            workflow_name="test_workflow",
            url="https://example.com/page",
            status=WorkflowStepStatus.PENDING,
            steps=steps,
            created_at="2024-01-15T10:00:00Z",
            updated_at="2024-01-15T10:00:00Z"
        )

        json_str = workflow.model_dump_json()
        data = json.loads(json_str)

        assert data["request_id"] == "req-123"
        assert data["workflow_name"] == "test_workflow"
        assert data["status"] == "pending"
        assert len(data["steps"]) == 1

    def test_workflow_instance_json_deserialization(self):
        """Test workflow instance JSON deserialization."""
        from models.workflow_models import WorkflowInstance

        json_data = {
            "request_id": "req-456",
            "workflow_name": "test_workflow",
            "url": "https://example.com/page",
            "status": "pending",
            "steps": [
                {"name": "step1", "status": "pending", "started_at": None, "completed_at": None, "error_message": None}
            ],
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
            "metadata": {}
        }

        workflow = WorkflowInstance(**json_data)

        assert workflow.request_id == "req-456"
        assert workflow.workflow_name == "test_workflow"
        assert len(workflow.steps) == 1
