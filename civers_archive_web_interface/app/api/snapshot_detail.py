"""
Snapshot detail API endpoint implementation.

This module provides the GET /api/snapshots/{snapshot_id} endpoint for individual snapshot details.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ..models.snapshot import Snapshot
from ..models.responses import ErrorResponse
from ..custom_exceptions.exceptions.api_exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Snapshots"])


class ArtifactInfo(BaseModel):
    """Information about an artifact file."""
    available: bool = Field(..., description="Whether the artifact is available")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    download_url: Optional[str] = Field(None, description="URL to download the artifact")


class SnapshotDetail(BaseModel):
    """Detailed snapshot information for individual snapshot view."""
    
    snapshot_id: str = Field(..., description="Unique snapshot identifier")
    timestamp: str = Field(..., description="Capture timestamp in ISO format")
    readable_timestamp: str = Field(..., description="Human-readable timestamp")
    original_url: str = Field(..., description="The original URL that was archived")
    title: Optional[str] = Field(None, description="Page title from metadata")
    
    # Artifact availability and links
    artifacts: Dict[str, ArtifactInfo] = Field(
        default_factory=dict,
        description="Information about available artifacts"
    )
    
    # Complete metadata from metadata.json
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Complete metadata from snapshot"
    )
    
    # Additional computed fields
    artifact_count: int = Field(..., description="Total number of available artifacts")
    has_replay_content: bool = Field(..., description="Whether WACZ or WARC content is available for replay")
    status_code: Optional[int] = Field(None, description="HTTP status code from metadata")
    content_type: Optional[str] = Field(None, description="Content type from metadata")
    content_length: Optional[int] = Field(None, description="Content length from metadata")

    @classmethod
    def from_snapshot(cls, snapshot: Snapshot, base_url: str = "", allowed_artifact_types: set = None) -> 'SnapshotDetail':
        """
        Convert a Snapshot model to SnapshotDetail with computed fields.
        
        Args:
            snapshot: Snapshot object from storage
            base_url: Base URL for constructing download links
            allowed_artifact_types: Set of allowed artifact types (loads from config if not provided)
            
        Returns:
            SnapshotDetail with all computed fields
        """
        # Fallback to common types if no config provided
        if allowed_artifact_types is None:
            allowed_artifact_types = {
                "archive.wacz", "archive.warc", "metadata.json", "screenshot.png",
                "singlefile.html", "document.html",
                "dom-snapshot.html", "archive_generator_metadata.json"
            }
        
        # Calculate file sizes if possible
        artifacts_info = {}
        for artifact_type in allowed_artifact_types:
            is_available = artifact_type in snapshot.available_artifacts
            size_bytes = None
            download_url = None
            
            if is_available:
                # Try to get file size if folder path is available
                if snapshot.folder_path:
                    try:
                        artifact_path = Path(snapshot.folder_path) / artifact_type
                        if artifact_path.exists():
                            size_bytes = artifact_path.stat().st_size
                    except (OSError, AttributeError):
                        pass  # File size unavailable
                
                # Construct download URL
                download_url = f"{base_url}/api/artifacts/serve?snapshot_id={snapshot.snapshot_id}&type={artifact_type}"
            
            artifacts_info[artifact_type] = ArtifactInfo(
                available=is_available,
                size_bytes=size_bytes,
                download_url=download_url
            )
        
        # Check if replay content is available
        has_replay_content = snapshot.has_wacz or snapshot.has_warc
        
        return cls(
            snapshot_id=snapshot.snapshot_id,
            timestamp=snapshot.timestamp.isoformat(),
            readable_timestamp=snapshot.formatted_timestamp,
            original_url=str(snapshot.url),
            title=snapshot.title,
            artifacts=artifacts_info,
            metadata=snapshot.metadata,
            artifact_count=len(snapshot.available_artifacts),
            has_replay_content=has_replay_content,
            status_code=snapshot.status_code,
            content_type=snapshot.content_type,
            content_length=snapshot.content_length
        )


@router.get(
    "/snapshots/{snapshot_id}",
    response_model=SnapshotDetail,
    responses={
        404: {"model": ErrorResponse, "description": "Snapshot not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get detailed information about a specific snapshot",
    description="Retrieve comprehensive details about a snapshot including metadata, artifact availability, and download links"
)
async def get_snapshot_detail(
    request: Request,
    snapshot_id: str
):
    """
    Get detailed information about a specific snapshot.
    
    Args:
        snapshot_id: The unique identifier for the snapshot
        
    Returns:
        SnapshotDetail with comprehensive snapshot information
        
    Raises:
        HTTPException: 404 if snapshot not found, 500 for server errors
    """
    # Get storage service from app state
    storage_service = request.app.state.storage_service
    logger.debug(f"Fetching snapshot details for: {snapshot_id}")
    
    # Get snapshot from storage service
    snapshot = storage_service.get_snapshot_by_id(snapshot_id)
    
    if not snapshot:
        logger.warning(f"Snapshot not found: {snapshot_id}")
        raise ResourceNotFoundError("Snapshot", snapshot_id)
    
    # Convert from storage model to Pydantic model if needed
    if not isinstance(snapshot, Snapshot):
        snapshot = Snapshot.from_scanner_result(snapshot)
    
    # Get base URL for download links
    base_url = str(request.base_url).rstrip('/')
    
    # Get allowed artifact types from app config
    try:
        allowed_artifact_types = request.app.state.app_config.validation.allowed_artifact_types
    except AttributeError:
        allowed_artifact_types = None

    # Convert to detail response format
    snapshot_detail = SnapshotDetail.from_snapshot(snapshot, base_url, allowed_artifact_types)
    
    logger.debug(f"Returning snapshot details for {snapshot_id} (artifacts: {snapshot_detail.artifact_count})")
    
    return snapshot_detail