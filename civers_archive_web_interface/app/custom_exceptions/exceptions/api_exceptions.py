"""
Custom exception classes for API business logic.

These exceptions are raised by API routes and handled by middleware to create
consistent HTTP responses. This separation allows clean business logic in routes
and centralized error handling in middleware.
"""


class ResourceNotFoundError(Exception):
    """Raised when a requested resource (URL, snapshot, artifact) is not found."""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(f"{resource_type} '{resource_id}' not found")


class ArtifactNotFoundError(Exception):
    """Raised when a specific artifact is not found for a snapshot."""

    def __init__(self, artifact_type: str, snapshot_id: str):
        self.artifact_type = artifact_type
        self.snapshot_id = snapshot_id
        super().__init__(f"Artifact '{artifact_type}' not found for snapshot '{snapshot_id}'")


class ValidationError(Exception):
    """Raised when request parameters fail validation."""

    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message)