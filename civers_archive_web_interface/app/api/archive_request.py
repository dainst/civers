"""
Archive Request API Router.

This router handles submission of new archive requests from the web form.
It validates the request, stores it in the status database, and publishes
an event to Kafka for the orchestrator to process.
"""

import logging
import uuid
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException, status, Body
from pydantic import ValidationError

from ..models.archive_request_events import ArchiveRequestForm, OrchestratorRequestEvent
from ..services import KafkaProducerError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Archive Request"]
)


@router.post("/archive-request", status_code=status.HTTP_201_CREATED)
async def create_archive_request(
    request: Request,
    form_data: ArchiveRequestForm = Body(...)
):
    """
    Submit a new archive request.
    
    Validates the URL and domain, calculates a unique request_id,
    stores the request status, and publishes to Kafka.
    """
    domain_service = request.app.state.domain_service
    kafka_producer = request.app.state.kafka_producer
    status_service = request.app.state.request_status_service
    
    # 1. Validate that the URL matches the selected domain
    if not domain_service.validate_url_for_domain(form_data.url, form_data.domain):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL '{form_data.url}' does not match the selected domain pattern '{form_data.domain}'"
        )
    
    # 2. Match the URL to get the actual domain configuration (for workflow_name)
    domain_info = domain_service.match_url_to_domain(form_data.url)
    if not domain_info:
        # This shouldn't happen if validate_url_for_domain passed, but safe to check
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported domain"
        )
    
    # 3. Generate unique request_id
    request_id = str(uuid.uuid4())
    logger.info(f"Processing new archive request: {request_id} for {form_data.url}")
    
    # 4. Determine callback URL for orchestrator to send status updates
    # In Docker, orchestrator needs to reach web-interface via internal network
    # CALLBACK_BASE_URL should be set to "http://web-interface:8000" in docker-compose
    import os
    callback_base = os.getenv("CALLBACK_BASE_URL")
    if not callback_base:
        callback_base = str(request.base_url).rstrip('/')
    callback_url = f"{callback_base}/api/webhook/status"
    logger.debug(f"Using callback URL: {callback_url}")

    
    # 5. Store request in database
    db_success = status_service.create_request(
        request_id=request_id,
        url=form_data.url,
        domain=form_data.domain,
        callback_url=callback_url
    )
    
    if not db_success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store request in database"
        )
    
    # 6. Publish to Kafka
    if not kafka_producer.is_enabled:
        logger.warning(f"Kafka is disabled. Request {request_id} stored in DB but not published.")
        # We'll still return 201 because it's stored and could be processed later or manually
        return {
            "status": "stored_locally",
            "message": "Archive request stored locally, but Kafka is disabled. It will not be sent to the orchestrator automatically.",
            "request_id": request_id,
            "url": form_data.url
        }
    
    try:
        # Create the orchestrator request event
        event = OrchestratorRequestEvent(
            request_id=request_id,
            url=form_data.url,
            workflow_name=None,  # Orchestrator will auto-detect from domain
            priority=1,  # System default
            callback_url=callback_url,
            metadata={
                "source": "web_interface_form",
                "original_domain_selection": form_data.domain
            }
        )
        
        # Publish to Kafka
        published = await kafka_producer.publish_event(
            topic_key="orchestrator_requests",
            event_data=event.model_dump()
        )
        
        if not published:
            # Update status to failed in DB
            status_service.update_status(
                request_id=request_id,
                status="failed",
                error_message="Failed to publish to Kafka"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Kafka service temporarily unavailable. Please try again later."
            )
            
        logger.info(f"✅ Successfully published archive request {request_id} to Kafka")
        
        return {
            "status": "submitted",
            "message": "Archive request successfully submitted and sent to orchestrator.",
            "request_id": request_id,
            "url": form_data.url
        }
        
    except KafkaProducerError as e:
        logger.error(f"Kafka error archiving {form_data.url}: {e}")
        status_service.update_status(
            request_id=request_id,
            status="failed",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Kafka communication error: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error processing archive request {request_id}")
        status_service.update_status(
            request_id=request_id,
            status="failed",
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/request-status/{request_id}")
async def get_request_status(
    request: Request,
    request_id: str
):
    """
    Get the current status of an archive request.
    
    This endpoint is polled by the status page to show real-time progress.
    
    Returns:
        JSON with status, current_step, completed_steps, error_message, snapshot_id, url_id
    """
    from ..utils.url_parser import generate_url_id
    
    status_service = request.app.state.request_status_service
    
    record = status_service.get_request(request_id)
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request {request_id} not found"
        )
    
    # Generate url_id from the URL for archive page linking
    url = record.get("url")
    url_id = generate_url_id(url) if url else None
    
    return {
        "request_id": record.get("request_id"),
        "status": record.get("status", "unknown"),
        "url": url,
        "url_id": url_id,
        "domain": record.get("domain"),
        "current_step": record.get("current_step"),
        "completed_steps": record.get("completed_steps", []),
        "error_message": record.get("error_message"),
        "snapshot_id": record.get("snapshot_id"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at")
    }

