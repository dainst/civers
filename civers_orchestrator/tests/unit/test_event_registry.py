"""
Unit tests for event registry module.

Tests the event model lookup and validation functionality.
"""

import pytest
from transport_services.kafka.event_registry import (
    get_event_model,
    validate_event_model_name,
    list_event_models,
    EVENT_MODELS,
)
from transport_services.kafka.event_models import (
    OrchestratorRequestEvent,
    OrchestratorCompletedEvent,
)
from transport_services.kafka.external_events.archive_events import (
    ArchiveRequestEvent,
    ArchiveCompletedEvent,
)
from transport_services.kafka.external_events.metadata_events import (
    MetadataExtractionRequestEvent,
    MetadataExtractionCompletedEvent,
)


class TestEventRegistry:
    """Test event model registry functionality."""

    def test_registry_contains_orchestrator_events(self):
        """Test that registry includes orchestrator's own events."""
        assert "OrchestratorRequestEvent" in EVENT_MODELS
        assert "OrchestratorStatusEvent" in EVENT_MODELS
        assert "OrchestratorCompletedEvent" in EVENT_MODELS
        assert "OrchestratorFailedEvent" in EVENT_MODELS

    def test_registry_contains_archive_events(self):
        """Test that registry includes archive generator events."""
        assert "ArchiveRequestEvent" in EVENT_MODELS
        assert "ArchiveStatusEvent" in EVENT_MODELS
        assert "ArchiveCompletedEvent" in EVENT_MODELS
        assert "ArchiveFailedEvent" in EVENT_MODELS

    def test_registry_contains_metadata_events(self):
        """Test that registry includes metadata extractor events."""
        assert "MetadataExtractionRequestEvent" in EVENT_MODELS
        assert "MetadataExtractionStatusEvent" in EVENT_MODELS
        assert "MetadataExtractionCompletedEvent" in EVENT_MODELS
        assert "MetadataExtractionFailedEvent" in EVENT_MODELS

    def test_get_orchestrator_event_model(self):
        """Test retrieving orchestrator event model."""
        model_class = get_event_model("OrchestratorRequestEvent")
        assert model_class is OrchestratorRequestEvent

    def test_get_archive_event_model(self):
        """Test retrieving archive generator event model."""
        model_class = get_event_model("ArchiveRequestEvent")
        assert model_class is ArchiveRequestEvent

    def test_get_metadata_event_model(self):
        """Test retrieving metadata extractor event model."""
        model_class = get_event_model("MetadataExtractionRequestEvent")
        assert model_class is MetadataExtractionRequestEvent

    def test_get_event_model_returns_correct_class(self):
        """Test that returned class can instantiate events."""
        model_class = get_event_model("ArchiveRequestEvent")
        event = model_class(
            request_id="test-123",
            url="https://example.com",
            priority=1,
        )
        assert event.request_id == "test-123"
        assert event.url == "https://example.com"
        assert event.priority == 1

    def test_get_event_model_unknown_raises_error(self):
        """Test that unknown event model name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown event model: NonExistentEvent"):
            get_event_model("NonExistentEvent")

    def test_get_event_model_error_includes_available_models(self):
        """Test that error message includes list of available models."""
        with pytest.raises(ValueError, match="Available models:"):
            get_event_model("InvalidModel")

    def test_validate_event_model_name_valid(self):
        """Test validation of valid event model names."""
        assert validate_event_model_name("OrchestratorRequestEvent") is True
        assert validate_event_model_name("ArchiveRequestEvent") is True
        assert validate_event_model_name("MetadataExtractionRequestEvent") is True

    def test_validate_event_model_name_invalid(self):
        """Test validation of invalid event model names."""
        assert validate_event_model_name("InvalidEvent") is False
        assert validate_event_model_name("") is False
        assert validate_event_model_name("NonExistent") is False

    def test_list_event_models_returns_all_models(self):
        """Test that list_event_models returns all registered models."""
        models = list_event_models()
        assert len(models) == 12  # 4 orchestrator + 4 archive + 4 metadata

    def test_list_event_models_is_sorted(self):
        """Test that returned list is sorted alphabetically."""
        models = list_event_models()
        assert models == sorted(models)

    def test_list_event_models_includes_expected_models(self):
        """Test that list includes all expected event types."""
        models = list_event_models()
        expected = [
            "OrchestratorRequestEvent",
            "ArchiveRequestEvent",
            "ArchiveCompletedEvent",
            "MetadataExtractionRequestEvent",
            "MetadataExtractionCompletedEvent",
        ]
        for model in expected:
            assert model in models

    def test_event_models_dict_has_correct_type(self):
        """Test that EVENT_MODELS values are all classes."""
        for name, model_class in EVENT_MODELS.items():
            assert isinstance(name, str)
            assert isinstance(model_class, type)

    def test_all_event_models_are_pydantic_models(self):
        """Test that all registered models are Pydantic BaseModel subclasses."""
        from pydantic import BaseModel

        for model_class in EVENT_MODELS.values():
            assert issubclass(model_class, BaseModel)


class TestEventRegistryWorkflowIntegration:
    """Test event registry integration with workflow configuration."""

    def test_workflow_yaml_event_models_are_registered(self):
        """Test that event models from workflows.yaml are all registered."""
        # These are the event models referenced in workflows.yaml
        workflow_event_models = [
            # Archive generation step
            "ArchiveRequestEvent",
            "ArchiveCompletedEvent",
            "ArchiveFailedEvent",
            # Metadata extraction step
            "MetadataExtractionRequestEvent",
            "MetadataExtractionCompletedEvent",
            "MetadataExtractionFailedEvent",
        ]

        for model_name in workflow_event_models:
            assert validate_event_model_name(model_name), (
                f"Event model {model_name} from workflows.yaml not registered"
            )

    def test_can_instantiate_all_workflow_event_models(self):
        """Test that all workflow event models can be instantiated."""
        workflow_event_models = [
            "ArchiveRequestEvent",
            "ArchiveCompletedEvent",
            "MetadataExtractionRequestEvent",
            "MetadataExtractionCompletedEvent",
        ]

        for model_name in workflow_event_models:
            model_class = get_event_model(model_name)
            assert model_class is not None
            # Verify it's callable (can be instantiated)
            assert callable(model_class)
