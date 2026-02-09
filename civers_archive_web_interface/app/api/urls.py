"""
URLs API endpoint implementation.

This module provides the GET /api/urls endpoint with pagination and sorting.
"""

import logging
import math
from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from ..models.url import ArchivedUrl
from ..models.snapshot import Snapshot
from ..models.snapshot_filters import SnapshotFilters, SnapshotSortOption, SnapshotSummary
from ..models.responses import PaginatedResponse, PaginationMeta, ErrorResponse
from ..custom_exceptions.exceptions.api_exceptions import ResourceNotFoundError, ValidationError
from configs import load_app_config

_app_config = load_app_config()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["URLs"])

class SortOption(str, Enum):
    """Available sorting options for URL list."""
    URL = "url"
    LAST_CAPTURED = "last_captured"
    SNAPSHOT_COUNT = "snapshot_count"


class UrlListSummary(BaseModel):
    """Summary model for URL list responses (without full snapshots)."""
    url_id: str
    original_url: str
    folder_name: str
    snapshot_count: int
    first_captured: str | None = None
    last_captured: str | None = None
    date_range: str | None = None

    @classmethod
    def from_archived_url(cls, archived_url: ArchivedUrl) -> 'UrlListSummary':
        """Convert ArchivedUrl to summary format."""
        return cls(
            url_id=archived_url.url_id,
            original_url=str(archived_url.original_url),
            folder_name=archived_url.folder_name,
            snapshot_count=archived_url.snapshot_count,
            first_captured=archived_url.first_captured.isoformat() if archived_url.first_captured else None,
            last_captured=archived_url.last_captured.isoformat() if archived_url.last_captured else None,
            date_range=archived_url.date_range
        )


class UrlDetail(UrlListSummary):
    """Detailed URL information including snapshots."""
    snapshots: list[SnapshotSummary] = []

@router.get(
    "/urls",
    response_model=PaginatedResponse[UrlListSummary],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="List all archived URLs",
    description="Retrieve a paginated list of all archived URLs with sorting options"
)
async def list_urls(
    request: Request,
    page: int = Query(_app_config.api.pagination.default_page, ge=1, description="Page number (1-based)"),
    limit: int = Query(_app_config.api.pagination.default_page_size, ge=1, le=_app_config.api.pagination.max_page_size, description=f"Number of items per page (1-{_app_config.api.pagination.max_page_size})"),
    sort: SortOption = Query(SortOption.URL, description="Sort order for results")
):
    """
    Get paginated list of archived URLs with sorting.
    
    Args:
        page: Page number (1-based, default: 1)
        limit: Items per page (1-100, default: 50)  
        sort: Sort option (url, last_captured, snapshot_count, default: url)
        
    Returns:
        PaginatedResponse containing URL summaries and pagination metadata
        
    Raises:
        HTTPException: For invalid parameters or server errors
    """
    # Get storage service from app state
    storage_service = request.app.state.storage_service
    logger.debug(f"Fetching URLs - page: {page}, limit: {limit}, sort: {sort}")
    
    # Get all URLs from storage service (with caching)
    url_dict = storage_service.get_all_urls()
    
    if not url_dict:
        logger.warning("No URLs found in storage")
        return PaginatedResponse[UrlListSummary](
            success=True,
            data=[],
            pagination=PaginationMeta.create(page=page, limit=limit, total_count=0)
        )
    
    # Convert to list of ArchivedUrl objects
    archived_urls = list(url_dict.values())
    
    # Apply sorting
    if sort == SortOption.URL:
        archived_urls.sort(key=lambda u: str(u.original_url).lower())
    elif sort == SortOption.LAST_CAPTURED:
        archived_urls.sort(key=lambda u: u.last_captured or datetime.min, reverse=True)
    elif sort == SortOption.SNAPSHOT_COUNT:
        archived_urls.sort(key=lambda u: u.snapshot_count, reverse=True)
    
    # Calculate pagination
    total_count = len(archived_urls)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit

    # Validate page bounds
    if page > 1 and start_idx >= total_count:
        total_pages = math.ceil(total_count / limit)
        raise ValidationError(f"Page {page} does not exist. Total pages: {total_pages}")
    
    # Get page slice
    page_urls = archived_urls[start_idx:end_idx]
    
    # Convert to summary format
    url_summaries = [UrlListSummary.from_archived_url(url) for url in page_urls]
    
    # Create pagination metadata
    pagination = PaginationMeta.create(page=page, limit=limit, total_count=total_count)
    
    logger.debug(f"Returning {len(url_summaries)} URLs (page {page}/{pagination.total_pages})")
    
    return PaginatedResponse[UrlListSummary](
        success=True,
        data=url_summaries,
        pagination=pagination
    )


@router.get(
    "/url/{url_id}",
    response_model=UrlDetail,
    responses={
        404: {"model": ErrorResponse, "description": "URL not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get summary for a specific URL",
    description="Retrieve summary information for a specific archived URL by its ID"
)
async def get_url_summary(
    request: Request,
    url_id: str
):
    """
    Get summary for a specific archived URL including snapshots.
    
    Returns:
        UrlDetail containing URL details and a list of snapshots
    """
    storage_service = request.app.state.storage_service
    archived_url = storage_service.get_url_by_id(url_id)
    
    if not archived_url:
        raise ResourceNotFoundError("URL", url_id)
        
    # Convert snapshots to summary format
    snapshots = [SnapshotSummary.from_snapshot(s) for s in archived_url.snapshots]
    
    # Sort snapshots newest first
    snapshots.sort(key=lambda s: s.timestamp, reverse=True)
    
    summary = UrlListSummary.from_archived_url(archived_url)
    
    return UrlDetail(
        **summary.model_dump(),
        snapshots=snapshots
    )


@router.get(
    "/urls/{url_id}/snapshots",
    response_model=PaginatedResponse[SnapshotSummary],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query parameters"},
        404: {"model": ErrorResponse, "description": "URL not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="List snapshots for a specific URL",
    description="Retrieve a paginated list of snapshots for a URL with filtering and sorting options"
)
async def list_snapshots(
    request: Request,
    url_id: str,
    page: int = Query(_app_config.api.pagination.default_page, ge=1, description="Page number (1-based)"),
    limit: int = Query(_app_config.api.pagination.default_page_size, ge=1, le=_app_config.api.pagination.max_page_size, description=f"Number of items per page (1-{_app_config.api.pagination.max_page_size})"),
    sort: SnapshotSortOption = Query(SnapshotSortOption.TIMESTAMP_DESC, description="Sort order for results"),
    from_date: Optional[str] = Query(None, description="Filter snapshots from date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Filter snapshots to date (YYYY-MM-DD)"),
    has_wacz: Optional[bool] = Query(None, description="Filter by WACZ availability"),
    has_screenshot: Optional[bool] = Query(None, description="Filter by screenshot availability"),
    has_singlefile: Optional[bool] = Query(None, description="Filter by SingleFile availability"),
    has_document: Optional[bool] = Query(None, description="Filter by document HTML availability"),
    status_code: Optional[int] = Query(None, ge=100, le=599, description="Filter by HTTP status code")
):
    """
    Get paginated list of snapshots for a specific URL with filtering and sorting.
    
    Args:
        url_id: URL identifier (e.g., 'example_com_home_page')
        page: Page number (1-based, default: 1)
        limit: Items per page (1-100, default: 50)  
        sort: Sort option (timestamp, timestamp_asc, title, status_code, default: timestamp)
        from_date: Filter from date (YYYY-MM-DD format)
        to_date: Filter to date (YYYY-MM-DD format)
        has_wacz: Filter by WACZ file availability
        has_screenshot: Filter by screenshot availability
        has_singlefile: Filter by SingleFile HTML availability
        has_document: Filter by document HTML availability
        status_code: Filter by HTTP status code (100-599)
        
    Returns:
        PaginatedResponse containing snapshot summaries and pagination metadata
        
    Raises:
        HTTPException: For invalid parameters, URL not found, or server errors
    """
    # Get storage service from app state
    storage_service = request.app.state.storage_service
    logger.debug(f"Fetching snapshots for URL '{url_id}' - page: {page}, limit: {limit}, sort: {sort}")
    
    # Get specific URL from storage service
    archived_url = storage_service.get_url_by_id(url_id)
    
    if not archived_url:
        raise ResourceNotFoundError("URL", url_id)
        
    # Create filters object from query parameters
    try:
        filters = SnapshotFilters(
            from_date=from_date,
            to_date=to_date,
            has_wacz=has_wacz,
            has_screenshot=has_screenshot,
            has_singlefile=has_singlefile,
            has_document=has_document,
            status_code=status_code
        )
    except Exception as e:
        raise ValidationError(f"Invalid filter parameters: {str(e)}")
    
    # Get snapshots and convert to Pydantic models
    snapshots = [Snapshot.from_scanner_result(s) for s in archived_url.snapshots]
    
    # Apply filters
    filtered_snapshots = [s for s in snapshots if filters.applies_to_snapshot(s)]
    
    if not filtered_snapshots:
        logger.debug(f"No snapshots found for URL '{url_id}' with applied filters")
        return PaginatedResponse[SnapshotSummary](
            success=True,
            data=[],
            pagination=PaginationMeta.create(page=page, limit=limit, total_count=0)
        )
    
    # Apply sorting
    if sort == SnapshotSortOption.TIMESTAMP_DESC:
        filtered_snapshots.sort(key=lambda s: s.timestamp, reverse=True)
    elif sort == SnapshotSortOption.TIMESTAMP_ASC:
        filtered_snapshots.sort(key=lambda s: s.timestamp)
    elif sort == SnapshotSortOption.TITLE:
        filtered_snapshots.sort(key=lambda s: s.title or "")
    elif sort == SnapshotSortOption.STATUS_CODE:
        filtered_snapshots.sort(key=lambda s: s.status_code or 0, reverse=True)
    
    # Calculate pagination
    total_count = len(filtered_snapshots)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit

    # Validate page bounds
    if page > 1 and start_idx >= total_count:
        total_pages = math.ceil(total_count / limit)
        raise ValidationError(f"Page {page} does not exist. Total pages: {total_pages}")
    
    # Get page slice
    page_snapshots = filtered_snapshots[start_idx:end_idx]
    
    # Convert to summary format
    snapshot_summaries = [SnapshotSummary.from_snapshot(snapshot) for snapshot in page_snapshots]
    
    # Create pagination metadata
    pagination = PaginationMeta.create(page=page, limit=limit, total_count=total_count)
    
    logger.debug(f"Returning {len(snapshot_summaries)} snapshots for URL '{url_id}' (page {page}/{pagination.total_pages})")
    
    return PaginatedResponse[SnapshotSummary](
        success=True,
        data=snapshot_summaries,
        pagination=pagination
    )


