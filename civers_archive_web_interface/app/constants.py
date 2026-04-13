"""
Application constants for Civers Archive Web Interface.

This module contains only truly immutable constants that define the API contract
and should NOT be configurable (changing them would break logic/integrations).

For configurable values, use AppConfig from configs module.
"""

from enum import StrEnum
from typing import Final


class RequestStatus(StrEnum):
    """
    Status values for archive requests.
    
    These are enum-like constants that define the API contract.
    They should NOT be configurable as they are used for logic comparisons
    and changing them would break integrations with orchestrator/frontend.
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    STORED_LOCALLY = "stored_locally"
    SUBMITTED = "submitted"
    UNKNOWN = "unknown"


class HealthStatus(StrEnum):
    """Health check status values."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


# SQL field allowlists - Security constants, not configurable
# These define which fields can be dynamically updated in SQL queries
# to prevent SQL injection attacks
ALLOWED_REQUEST_STATUS_FIELDS: Final[frozenset] = frozenset({
    "status",
    "workflow_name",
    "current_step",
    "completed_steps",
    "error_message",
    "snapshot_id",
    "updated_at"
})


# API path prefixes - Structural constants that define the API contract
API_PREFIX: Final[str] = "/api"
WEBHOOK_STATUS_PATH: Final[str] = "/api/webhook/status"

# FastAPI built-in paths that should be treated as API requests
FASTAPI_API_PATHS: Final[frozenset] = frozenset({
    '/docs', '/openapi.json', '/redoc'
})


# Metadata source identifiers for tracking request origins
class MetadataSource(StrEnum):
    """Source identifiers for tracking where requests originated."""
    WEB_INTERFACE_FORM = "web_interface_form"
    API_UPLOAD = "api_upload"
    WEBHOOK = "webhook"
