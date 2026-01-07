"""
Page rendering routes for the web interface.

This module provides HTML page endpoints that render templates for the web interface.
"""

import logging
import json
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response

logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Create router for page routes
router = APIRouter(tags=["Pages"])


@router.get("/archive/{url_id}", response_class=HTMLResponse)
async def archive_page(request: Request, url_id: str):
    """
    Render the archive page for a specific URL.
    
    This page displays all snapshots for a given URL with sorting, filtering,
    and pagination controls.
    
    Args:
        request: FastAPI request object
        url_id: URL identifier (e.g., 'example_com_home_page')
        
    Returns:
        HTMLResponse: Rendered archive page template
        
    Raises:
        HTTPException: If URL ID is invalid or not found
    """
    logger.debug(f"Rendering archive page for URL ID: {url_id}")
    
    # Get storage service to validate URL exists
    storage_service = request.app.state.storage_service
    archived_url = storage_service.get_url_by_id(url_id)
    
    if not archived_url:
        logger.warning(f"URL ID not found: {url_id}")
        raise HTTPException(
            status_code=404, 
            detail=f"Archive not found for URL ID: {url_id}"
        )
    
    # Prepare context for template
    context = {
        "request": request,
        "title": f"Archive: {archived_url.original_url}",
        "url_id": url_id,
        "original_url": str(archived_url.original_url),
        "snapshot_count": archived_url.snapshot_count,
        "first_captured": archived_url.first_captured.isoformat() if archived_url.first_captured else None,
        "last_captured": archived_url.last_captured.isoformat() if archived_url.last_captured else None,
        "date_range": archived_url.date_range
    }
    
    logger.debug(f"Archive page context: {context}")
    
    return templates.TemplateResponse("url_archive.html", context)


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """
    Render the home page.
    
    Args:
        request: FastAPI request object
        
    Returns:
        HTMLResponse: Rendered home page template
    """
    logger.debug("Rendering home page")
    
    # Prepare domain list for the archive form
    domain_service = request.app.state.domain_service
    domains = domain_service.get_domain_names_for_dropdown()
    
    context = {
        "request": request,
        "title": "Civers Archive Web Interface",
        "domains_json": json.dumps(domains)
    }
    
    return templates.TemplateResponse("index.html", context)


@router.get("/archive-request", response_class=HTMLResponse)
async def archive_request_page(request: Request):
    """
    Render the archive request form page.
    """
    domain_service = request.app.state.domain_service
    domains = domain_service.get_domain_names_for_dropdown()
    
    context = {
        "request": request,
        "title": "Request Site Archive",
        "domains_json": json.dumps(domains)
    }
    
    return templates.TemplateResponse("archive_request.html", context)


@router.get("/status/{request_id}", response_class=HTMLResponse)
async def status_page(request: Request, request_id: str):
    """
    Render the archive request status page.
    """
    # This status page will be implemented in detail in Task 8
    # For now, it's just a placeholder template
    context = {
        "request": request,
        "title": f"Archive Status: {request_id}",
        "request_id": request_id
    }
    
    return templates.TemplateResponse("status.html", context)


@router.get("/my-requests", response_class=HTMLResponse)
async def my_requests_page(request: Request):
    """
    Render the My Requests page where users can view all their archive requests.
    
    Requests are stored client-side in localStorage and their statuses are
    fetched dynamically via the API.
    """
    context = {
        "request": request,
        "title": "My Archive Requests"
    }
    
    return templates.TemplateResponse("my_requests.html", context)


@router.get("/replay/{snapshot_id}", response_class=HTMLResponse)
async def replay_page(request: Request, snapshot_id: str, view_type: str = Query(None)):
    """
    Render the replay page for a specific snapshot.
    
    This page displays WARC or SingleFile content for a snapshot with metadata
    header, view toggle, and breadcrumb navigation.
    
    Args:
        request: FastAPI request object
        snapshot_id: Snapshot identifier
        view_type: Optional view type ('warc' or 'singlefile')
        
    Returns:
        HTMLResponse: Rendered replay page template
        
    Raises:
        HTTPException: If snapshot ID is invalid or not found
    """
    logger.debug(f"Rendering replay page for snapshot ID: {snapshot_id}")
    
    try:
        # Get storage service to validate snapshot exists
        storage_service = request.app.state.storage_service
        logger.debug(f"Got storage service: {storage_service}")
        snapshot = storage_service.get_snapshot_by_id(snapshot_id)
        logger.debug(f"Got snapshot: {snapshot}")
    except Exception as e:
        logger.error(f"Error getting snapshot: {e}")
        raise
    
    if not snapshot:
        logger.warning(f"Snapshot ID not found: {snapshot_id}")
        raise HTTPException(
            status_code=404, 
            detail=f"Snapshot not found: {snapshot_id}"
        )
    
    # Get parent URL for breadcrumb navigation
    archived_url = storage_service.find_url_by_original_url(str(snapshot.url))
    
    # Determine available view types
    available_views = []
    if snapshot.has_wacz:
        available_views.append('wacz')
    if snapshot.has_singlefile:
        available_views.append('singlefile')

    # Set default view if not specified
    if not view_type and available_views:
        view_type = 'wacz' if 'wacz' in available_views else available_views[0]
    
    # Validate requested view type is available
    if view_type and view_type not in available_views:
        logger.warning(f"Requested view type '{view_type}' not available for snapshot {snapshot_id}")
        view_type = available_views[0] if available_views else None
    
    # Prepare context for template
    context = {
        "request": request,
        "title": f"Replay: {snapshot.title or archived_url.original_url if archived_url else 'Snapshot'}",
        "snapshot_id": snapshot_id,
        "snapshot": {
            "snapshot_id": snapshot.snapshot_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "title": snapshot.title,
            "status_code": snapshot.status_code,
            "available_artifacts": snapshot.available_artifacts,
            "url": str(snapshot.url)  # The actual archived URL (may include query params)
        },
        "archived_url": {
            "url_id": archived_url.url_id if archived_url else None,
            "original_url": str(archived_url.original_url) if archived_url else None
        } if archived_url else None,
        "current_view": view_type,
        "available_views": available_views
    }

    logger.debug(f"Replay page context: {context}")

    return templates.TemplateResponse("replay.html", context)



@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """
    Return a minimal favicon to prevent 404 errors.

    Returns empty response with appropriate content type.
    """
    # Return empty response with ICO content type to prevent 404s
    return Response(content=b"", media_type="image/x-icon")