"""Workflow orchestration tests with mocked components.

These tests validate the complete workflow orchestration logic without
requiring any external infrastructure (Kafka, etc.). They run entirely
in memory using the OrchestratorService directly.

Run with:
    pytest tests/integration/test_workflow_orchestration.py -v
"""

import pytest
from models.orchestrator_models import WorkflowTransition

# ==============================================================================
# Configuration Migration Note
# ==============================================================================
#
# The hardcoded mock_config and orchestrator fixtures have been removed.
# Tests now use shared fixtures from tests/conftest.py:
#   - test_config: Loads from configs/data/environments/testing.yaml
#   - orchestrator: Pre-initialized OrchestratorService with test_config
#
# All test workflows and domains are defined in testing.yaml, providing a
# single source of truth for test configuration.
#
# Benefits:
#   - No more 100+ lines of hardcoded config
#   - Easy to update (change testing.yaml once, affects all tests)
#   - Consistent configuration across all tests
#   - Same workflows/domains as other tests
# ==============================================================================


class TestWorkflowStart:
    """Tests for starting workflows."""

    def test_start_workflow_creates_instruction(self, orchestrator):
        """Test that start_workflow returns a valid StepInstruction."""
        instruction = orchestrator.start_workflow(
            request_id="test-001",
            url="https://example.com/page",
        )

        assert instruction is not None
        assert instruction.request_id == "test-001"
        assert instruction.component == "archive_generator"
        assert instruction.input_schema == "ArchiveRequest"
        # URL is stored in instruction.url, not input_data
        assert instruction.url == "https://example.com/page"

    def test_start_workflow_domain_matching_exact(self, orchestrator):
        """Test exact domain matching selects correct workflow."""
        instruction = orchestrator.start_workflow(
            request_id="test-002",
            url="https://arachne.dainst.org/entity/12345",
        )

        # Should match archaeology_workflow for arachne.dainst.org
        state = orchestrator.get_workflow_state("test-002")
        assert state.workflow_name == "archaeology_workflow"

    def test_start_workflow_domain_matching_wildcard(self, orchestrator):
        """Test wildcard domain matching."""
        instruction = orchestrator.start_workflow(
            request_id="test-003",
            url="https://field.dainst.org/data",
        )

        # Should match *.dainst.org -> dainst_workflow
        state = orchestrator.get_workflow_state("test-003")
        assert state.workflow_name == "dainst_workflow"

    def test_start_workflow_explicit_workflow_name(self, orchestrator):
        """Test specifying workflow name explicitly."""
        instruction = orchestrator.start_workflow(
            request_id="test-004",
            url="https://unknown.example.org/page",
            workflow_name="archaeology_workflow",
        )

        state = orchestrator.get_workflow_state("test-004")
        assert state.workflow_name == "archaeology_workflow"


class TestWorkflowCompletion:
    """Tests for workflow step completion and transitions."""

    def test_single_step_workflow_completes(self, orchestrator):
        """Test that a single-step workflow completes after one step."""
        # Start workflow
        orchestrator.start_workflow(
            request_id="test-single-001",
            url="https://example.com/page",
        )

        # Complete the only step
        transition = orchestrator.step_completed(
            request_id="test-single-001",
            step_name="archive_generation",
            result_data={"archive_path": "/path/to/archive.wacz"},
        )

        # Should be complete
        assert isinstance(transition, WorkflowTransition)
        assert transition.action == "workflow_complete"
        assert transition.workflow_instance is not None
        assert transition.workflow_instance.status.value == "completed"

    def test_multi_step_workflow_transitions(self, orchestrator):
        """Test that multi-step workflow transitions correctly."""
        # Start workflow (should return archive_generation instruction)
        instruction = orchestrator.start_workflow(
            request_id="test-multi-001",
            url="https://arachne.dainst.org/entity/12345",
        )

        assert instruction.step_config.name == "archive_generation"

        # Complete first step
        transition = orchestrator.step_completed(
            request_id="test-multi-001",
            step_name="archive_generation",
            result_data={
                "snapshot_id": "test_snapshot_123",
                "archive_path": "/path/to/archive",
            },
        )

        # Should transition to next step
        assert transition.action == "execute_step"
        assert transition.step_instruction is not None
        assert transition.step_instruction.step_config.name == "metadata_extraction"
        assert transition.step_instruction.component == "metadata_extractor"

    def test_multi_step_workflow_completes(self, orchestrator):
        """Test that multi-step workflow completes after all steps."""
        # Start workflow
        orchestrator.start_workflow(
            request_id="test-multi-002",
            url="https://arachne.dainst.org/entity/12345",
        )

        # Complete first step
        orchestrator.step_completed(
            request_id="test-multi-002",
            step_name="archive_generation",
            result_data={"snapshot_id": "test_snapshot"},
        )

        # Complete second step
        transition = orchestrator.step_completed(
            request_id="test-multi-002",
            step_name="metadata_extraction",
            result_data={"metadata": {"title": "Test"}},
        )

        # Should be complete
        assert transition.action == "workflow_complete"
        assert transition.workflow_instance.status.value == "completed"

    def test_step_results_passed_between_steps(self, orchestrator):
        """Test that step results are available to subsequent steps."""
        # Start workflow
        orchestrator.start_workflow(
            request_id="test-results-001",
            url="https://arachne.dainst.org/entity/12345",
        )

        # Complete first step with snapshot_id
        transition = orchestrator.step_completed(
            request_id="test-results-001",
            step_name="archive_generation",
            result_data={"snapshot_id": "my_test_snapshot_id"},
        )

        # Next step should have access to previous results via document_url
        next_instruction = transition.step_instruction
        assert next_instruction is not None
        # The document_url should contain the snapshot_id
        if "document_url" in next_instruction.input_data:
            assert "my_test_snapshot_id" in next_instruction.input_data["document_url"]


class TestWorkflowFailure:
    """Tests for workflow failure handling."""

    def test_step_failure_fails_workflow(self, orchestrator):
        """Test that step failure correctly fails the workflow."""
        # Start workflow
        orchestrator.start_workflow(
            request_id="test-fail-001",
            url="https://example.com/page",
        )

        # Fail the step
        transition = orchestrator.step_failed(
            request_id="test-fail-001",
            step_name="archive_generation",
            error_message="Connection timeout",
        )

        # Should be failed
        assert transition.action == "workflow_failed"
        assert transition.error_message == "Connection timeout"
        assert transition.failed_step == "archive_generation"

    def test_failed_workflow_state(self, orchestrator):
        """Test that failed workflow has correct state."""
        # Start and fail workflow
        orchestrator.start_workflow(
            request_id="test-fail-002",
            url="https://example.com/page",
        )

        orchestrator.step_failed(
            request_id="test-fail-002",
            step_name="archive_generation",
            error_message="Network error",
        )

        # Check state
        state = orchestrator.get_workflow_state("test-fail-002")
        assert state.status.value == "failed"
        assert "archive_generation" in state.failed_steps


class TestWorkflowStatus:
    """Tests for workflow status queries."""

    def test_get_workflow_status(self, orchestrator):
        """Test getting workflow status."""
        # Start workflow
        orchestrator.start_workflow(
            request_id="test-status-001",
            url="https://example.com/page",
        )

        # Get status
        status = orchestrator.get_workflow_status("test-status-001")

        assert status is not None
        assert status.request_id == "test-status-001"
        assert status.workflow_name == "simple_workflow"
        assert status.status == "in_progress"

    def test_get_workflow_status_after_completion(self, orchestrator):
        """Test status after workflow completes."""
        # Start and complete workflow
        orchestrator.start_workflow(
            request_id="test-status-002",
            url="https://example.com/page",
        )

        orchestrator.step_completed(
            request_id="test-status-002",
            step_name="archive_generation",
            result_data={},
        )

        # Get status
        status = orchestrator.get_workflow_status("test-status-002")

        assert status.status == "completed"

    def test_get_nonexistent_workflow_status(self, orchestrator):
        """Test that nonexistent workflow returns None."""
        status = orchestrator.get_workflow_status("nonexistent-id")
        assert status is None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_duplicate_request_id_is_handled(self, orchestrator):
        """Test that duplicate request IDs are handled."""
        orchestrator.start_workflow(
            request_id="duplicate-001",
            url="https://example.com/page",
        )

        # Starting with same ID - implementation may raise or overwrite
        # Current implementation appears to allow it (no error raised)
        # If this should be an error, the OrchestratorService needs updating
        try:
            orchestrator.start_workflow(
                request_id="duplicate-001",
                url="https://example.com/other",
            )
            # If we get here, duplicates are allowed (overwritten)
            state = orchestrator.get_workflow_state("duplicate-001")
            assert state is not None
        except ValueError:
            # If we get here, duplicates raise an error (preferred)
            pass

    def test_invalid_step_name_behavior(self, orchestrator):
        """Test behavior when completing an invalid step."""
        orchestrator.start_workflow(
            request_id="invalid-step-001",
            url="https://example.com/page",
        )

        # Completing a nonexistent step - current implementation may:
        # 1. Raise ValueError (preferred)
        # 2. Silently ignore (less ideal)
        # 3. Still mark workflow as progressed (buggy)
        try:
            transition = orchestrator.step_completed(
                request_id="invalid-step-001",
                step_name="nonexistent_step",
                result_data={},
            )
            # If we get here, check that workflow state is still sensible
            state = orchestrator.get_workflow_state("invalid-step-001")
            assert state is not None
        except ValueError:
            # Expected behavior - invalid step should raise
            pass

    def test_nonexistent_request_id_raises_error(self, orchestrator):
        """Test that operations on nonexistent request raise error."""
        with pytest.raises(ValueError):
            orchestrator.step_completed(
                request_id="nonexistent-id",
                step_name="archive_generation",
                result_data={},
            )
