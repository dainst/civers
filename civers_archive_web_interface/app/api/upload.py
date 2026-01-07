"""
Upload API endpoint implementation.

This module provides the POST /api/upload endpoint for uploading archive files
(WACZ, screenshots, SingleFile HTML, metadata.json) with multipart form data support.
"""

import logging
from typing import Optional, List
from io import BytesIO
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..custom_exceptions.exceptions.api_exceptions import ValidationError
from ..storage.providers.storage_provider_interface import StorageError
from ..models.responses import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Upload"])


class UploadResponse(BaseModel):
    """Response model for successful upload."""
    success: bool = Field(..., description="Whether the upload was successful")
    snapshot_id: str = Field(..., description="Generated snapshot ID")
    url: str = Field(..., description="URL that was archived")
    artifacts_uploaded: List[str] = Field(..., description="List of uploaded artifact filenames")
    message: str = Field(..., description="Success message")


class UploadRequest(BaseModel):
    """Request model for upload parameters (for documentation)."""
    url: str = Field(..., description="URL being archived (e.g., 'https://example.com/page')")
    request_id: str = Field(..., description="Unique request identifier")
    allow_existing: bool = Field(
        default=False,
        description="If true, allow adding files to existing snapshot (idempotent operation)"
    )
    files: List[UploadFile] = Field(..., description="Archive files to upload")


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP address from request for logging."""
    forwarded_for = request.headers.get('x-forwarded-for')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()

    real_ip = request.headers.get('x-real-ip')
    if real_ip:
        return real_ip

    if request.client:
        return request.client.host

    return None


@router.post(
    "/upload",
    response_model=UploadResponse,
    responses={
        200: {"model": UploadResponse, "description": "Files uploaded successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters or files"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Upload archive files",
    description="""
Upload archive files for a URL snapshot. Supports multiple file types:
- archive.wacz (WACZ archive)
- screenshot.png (Screenshot image)
- singlefile.html (SingleFile HTML)
- metadata.json (Metadata JSON)

Files are stored in structured directories: archives/{domain}/{path}/req_{request_id}_{timestamp}/

Supports idempotent operations: set allow_existing=true to add files to an existing snapshot.
"""
)
async def upload_files(
    request: Request,
    url: str = Form(..., description="URL being archived"),
    request_id: str = Form(..., description="Unique request identifier"),
    allow_existing: bool = Form(False, description="Allow adding to existing snapshot"),
    files: List[UploadFile] = File(..., description="Archive files to upload")
):
    """
    Upload archive files for a URL snapshot.

    Args:
        request: FastAPI request object
        url: URL being archived (e.g., 'https://example.com/page')
        request_id: Unique request identifier
        allow_existing: If True, allow adding files to existing snapshot
        files: List of uploaded files

    Returns:
        UploadResponse with snapshot details

    Raises:
        HTTPException: 400 for validation errors, 500 for server errors
    """
    client_ip = get_client_ip(request)
    storage_service = request.app.state.storage_service

    logger.info(
        f"Upload request from {client_ip}: url={url}, request_id={request_id}, "
        f"allow_existing={allow_existing}, file_count={len(files)}"
    )

    try:
        # Validate that we have files
        if not files:
            raise ValidationError("No files provided for upload")

        # Convert uploaded files to Dict[str, IO] format expected by storage
        file_streams = {}
        for upload_file in files:
            # Read file content into BytesIO
            content = await upload_file.read()
            file_streams[upload_file.filename] = BytesIO(content)

            logger.debug(
                f"Received file: {upload_file.filename} "
                f"({len(content)} bytes, content_type={upload_file.content_type})"
            )

        # Create snapshot using storage service
        snapshot = storage_service.create_snapshot(
            url=url,
            request_id=request_id,
            files=file_streams,
            allow_existing=allow_existing
        )

        logger.info(
            f"Successfully created snapshot {snapshot.snapshot_id} for URL '{url}' "
            f"with {len(snapshot.available_artifacts)} artifacts"
        )

        # Build success response
        response = UploadResponse(
            success=True,
            snapshot_id=snapshot.snapshot_id,
            url=str(snapshot.url),  # Convert HttpUrl to string
            artifacts_uploaded=snapshot.available_artifacts,
            message=f"Successfully uploaded {len(snapshot.available_artifacts)} artifact(s)"
        )

        return response

    except ValidationError as e:
        logger.warning(f"Validation error in upload: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except StorageError as e:
        error_msg = str(e)
        # Check if this is actually a validation error wrapped in StorageError
        if 'Invalid artifact type' in error_msg or 'Snapshot already exists' in error_msg:
            logger.warning(f"Validation error in storage: {e}")
            # Extract the actual error message from the wrapped error
            if ': ' in error_msg:
                error_msg = error_msg.split(': ', 1)[1]
            raise HTTPException(status_code=400, detail=error_msg)
        logger.error(f"Storage error in upload: {e}")
        raise HTTPException(status_code=500, detail=f"Storage error: {error_msg}")

    except Exception as e:
        logger.error(f"Unexpected error in upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get(
    "/upload/info",
    summary="Get upload endpoint information",
    description="Get information about the upload endpoint including allowed file types and constraints"
)
async def upload_info(request: Request):
    """
    Get information about the upload endpoint.

    Returns:
        Dictionary with upload endpoint information
    """
    validation_config = request.app.state.app_config.validation

    return {
        "endpoint": "/api/upload",
        "method": "POST",
        "content_type": "multipart/form-data",
        "form_fields": {
            "url": "URL being archived (required)",
            "request_id": "Unique request identifier (required)",
            "allow_existing": "Allow adding to existing snapshot (optional, default: false)",
            "files": "Archive files to upload (required, multiple allowed)"
        },
        "allowed_file_types": sorted(validation_config.allowed_artifact_types),
        "max_file_size": "Depends on server configuration",
        "example_curl": (
            "curl -X POST http://localhost:8000/api/upload \\\n"
            "  -F 'url=https://example.com/page' \\\n"
            "  -F 'request_id=abc123' \\\n"
            "  -F 'files=@archive.wacz' \\\n"
            "  -F 'files=@screenshot.png' \\\n"
            "  -F 'files=@metadata.json'"
        ),
        "idempotent_example": (
            "curl -X POST http://localhost:8000/api/upload \\\n"
            "  -F 'url=https://example.com/page' \\\n"
            "  -F 'request_id=abc123' \\\n"
            "  -F 'allow_existing=true' \\\n"
            "  -F 'files=@singlefile.html'"
        )
    }
