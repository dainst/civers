"""
Artifacts serving API endpoint implementation.

This module provides the GET /api/artifacts/serve endpoint for secure file downloads
with comprehensive security validation and proper streaming support.
"""

import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from ..utils import (
    validate_request_parameters,
    get_content_type,
    get_content_disposition,
    validate_file_path,
    log_access_attempt
)
from ..custom_exceptions.exceptions.api_exceptions import ResourceNotFoundError, ArtifactNotFoundError
from ..models.responses import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Artifacts"])


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP address from request for logging."""
    # Check for forwarded headers first (reverse proxy scenarios)
    forwarded_for = request.headers.get('x-forwarded-for')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    
    real_ip = request.headers.get('x-real-ip')
    if real_ip:
        return real_ip
    
    # Fall back to direct connection
    if request.client:
        return request.client.host
    
    return None


@router.get(
    "/artifacts/serve",
    responses={
        200: {"description": "Artifact file download"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        404: {"model": ErrorResponse, "description": "Snapshot or artifact not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Download artifact files",
    description="Securely serve artifact files (WACZ, screenshots, metadata, etc.) with proper headers and streaming support"
)
async def serve_artifact(
    request: Request,
    snapshot_id: str = Query(..., description="Snapshot identifier (e.g., 'req_test-request-1_20250904_061411')"),
    type: str = Query(..., alias="type", description="Artifact type (archive.wacz, screenshot.png, etc.)")
):
    """
    Serve artifact files with security validation and proper streaming.
    
    Args:
        snapshot_id: The unique identifier for the snapshot
        type: The type of artifact to serve (must be from allowed whitelist)
        
    Returns:
        FileResponse with the requested artifact file
        
    Raises:
        HTTPException: 400 for invalid parameters, 404 for missing files, 500 for server errors
    """
    client_ip = get_client_ip(request)
    
    # Step 1: Validate input parameters
    validation_config = request.app.state.app_config.validation
    validated_snapshot_id, validated_artifact_type = validate_request_parameters(snapshot_id, type, validation_config)
    
    # Step 2: Get storage service and validate snapshot exists
    storage_service = request.app.state.storage_service
    logger.debug(f"Serving artifact: {validated_snapshot_id}/{validated_artifact_type}")
    
    # Check if snapshot exists
    snapshot = storage_service.get_snapshot_by_id(validated_snapshot_id)
    if not snapshot:
        log_access_attempt(validated_snapshot_id, validated_artifact_type, client_ip, success=False, failure_reason="snapshot not found")
        raise ResourceNotFoundError("Snapshot", validated_snapshot_id)

    # Step 3: Check if specific artifact exists
    if not storage_service.artifact_exists(validated_snapshot_id, validated_artifact_type):
        log_access_attempt(validated_snapshot_id, validated_artifact_type, client_ip, success=False, failure_reason="artifact not found in snapshot")
        raise ArtifactNotFoundError(validated_artifact_type, validated_snapshot_id)

    # Step 4: Get artifact file path with security validation
    artifact_path = storage_service.get_artifact_path(validated_snapshot_id, validated_artifact_type)
    if not artifact_path:
        raise ArtifactNotFoundError(validated_artifact_type, validated_snapshot_id)

    # Validate the file path is within storage boundaries
    storage_root = Path(storage_service.provider.storage_path)
    validated_path = validate_file_path(Path(artifact_path), storage_root)

    # Step 5: Verify file actually exists on filesystem
    if not validated_path.exists():
        log_access_attempt(validated_snapshot_id, validated_artifact_type, client_ip, success=False, failure_reason="file does not exist")
        raise ArtifactNotFoundError(validated_artifact_type, validated_snapshot_id)

    # Step 6: Check if it's actually a file (not directory)
    if not validated_path.is_file():
        log_access_attempt(validated_snapshot_id, validated_artifact_type, client_ip, success=False, failure_reason="path is not a file")
        raise ArtifactNotFoundError(validated_artifact_type, validated_snapshot_id)
    
    # Step 7: Prepare response headers
    content_type = get_content_type(validated_artifact_type, validation_config)
    content_disposition = get_content_disposition(validated_artifact_type, validated_snapshot_id)
    
    # Additional security headers
    headers = {
        "Content-Type": content_type,
        "Content-Disposition": content_disposition,
        "X-Content-Type-Options": "nosniff",  # Prevent MIME sniffing
        "Cache-Control": "private, max-age=3600",  # Cache for 1 hour
    }
    
    # Step 8: Log successful access
    log_access_attempt(validated_snapshot_id, validated_artifact_type, client_ip, success=True)
    
    # Step 9: Return file response
    # For large files (like WACZ), FileResponse handles streaming automatically
    return FileResponse(
        path=str(validated_path),
        headers=headers,
        filename=f"{validated_snapshot_id}_{validated_artifact_type}"
    )