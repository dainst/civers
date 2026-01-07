"""
Pydantic models for Civers Archive Web Interface

This module provides type-safe data models for API requests/responses,
data validation, and automatic OpenAPI documentation generation.
"""

from .url import ArchivedUrl
from .snapshot import Snapshot
from .artifact import Artifact
from .responses import PaginatedResponse, ErrorResponse, SuccessResponse, PaginationMeta, CitationResponse
from .archive_request_events import (
    EventBaseModel,
    OrchestratorRequestEvent,
    ArchiveRequestForm,
)

__all__ = [
    # Core data models
    "ArchivedUrl",
    "Snapshot", 
    "Artifact",
    # Response models
    "PaginatedResponse",
    "ErrorResponse",
    "SuccessResponse",
    "PaginationMeta",
    "CitationResponse",
    # Archive request event models
    "EventBaseModel",
    "OrchestratorRequestEvent",
    "ArchiveRequestForm",
]