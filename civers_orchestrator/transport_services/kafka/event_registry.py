"""
Event Registry Module.

Central registry mapping event model names (from YAML config) to Python classes.
This enables dynamic event model lookup based on workflow configuration.
"""

from typing import Dict, Type
from pydantic import BaseModel

# Orchestrator's own event models
from transport_services.kafka.event_models import (
    OrchestratorRequestEvent,
    OrchestratorStatusEvent,
    OrchestratorCompletedEvent,
    OrchestratorFailedEvent,
)

# External service event models (copied into orchestrator)
from transport_services.kafka.external_events.archive_events import (
    ArchiveRequestEvent,
    ArchiveStatusEvent,
    ArchiveCompletedEvent,
    ArchiveFailedEvent,
)

from transport_services.kafka.external_events.metadata_events import (
    MetadataExtractionRequestEvent,
    MetadataExtractionStatusEvent,
    MetadataExtractionCompletedEvent,
    MetadataExtractionFailedEvent,
)


# Event model registry: string name -> Python class
EVENT_MODELS: Dict[str, Type[BaseModel]] = {
    # Orchestrator events
    "OrchestratorRequestEvent": OrchestratorRequestEvent,
    "OrchestratorStatusEvent": OrchestratorStatusEvent,
    "OrchestratorCompletedEvent": OrchestratorCompletedEvent,
    "OrchestratorFailedEvent": OrchestratorFailedEvent,
    # Archive generator events
    "ArchiveRequestEvent": ArchiveRequestEvent,
    "ArchiveStatusEvent": ArchiveStatusEvent,
    "ArchiveCompletedEvent": ArchiveCompletedEvent,
    "ArchiveFailedEvent": ArchiveFailedEvent,
    # Metadata extractor events
    "MetadataExtractionRequestEvent": MetadataExtractionRequestEvent,
    "MetadataExtractionStatusEvent": MetadataExtractionStatusEvent,
    "MetadataExtractionCompletedEvent": MetadataExtractionCompletedEvent,
    "MetadataExtractionFailedEvent": MetadataExtractionFailedEvent,
}


def get_event_model(model_name: str) -> Type[BaseModel]:
    """
    Get event model class by name.

    Args:
        model_name: Name of the event model (e.g. "ArchiveRequestEvent")

    Returns:
        Event model class

    Raises:
        ValueError: If model_name is not registered
    """
    if model_name not in EVENT_MODELS:
        available = ", ".join(sorted(EVENT_MODELS.keys()))
        raise ValueError(
            f"Unknown event model: {model_name}. "
            f"Available models: {available}"
        )
    return EVENT_MODELS[model_name]


def validate_event_model_name(model_name: str) -> bool:
    """
    Check if an event model name is registered.

    Args:
        model_name: Name to validate

    Returns:
        True if registered, False otherwise
    """
    return model_name in EVENT_MODELS


def list_event_models() -> list[str]:
    """
    Get list of all registered event model names.

    Returns:
        Sorted list of event model names
    """
    return sorted(EVENT_MODELS.keys())
