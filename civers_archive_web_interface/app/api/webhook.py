"""
Webhook API Router for status updates from the orchestrator.

This router provides an endpoint that the orchestrator calls (via callback_url)
to provide real-time updates on archive request progress.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException, status, Body
from pydantic import BaseModel, Field

from ..constants import RequestStatus

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/webhook",
    tags=["Webhook"]
)


class WebhookPayload(BaseModel):
    """
    Typed payload for status updates from the orchestrator.
    Can represent status change, completion, or failure.
    """
    request_id: str
    url: str
    workflow_name: Optional[str] = None
    status: str
    current_step: Optional[str] = None
    completed_steps: Optional[List[str]] = None
    failed_step: Optional[str] = None
    error_message: Optional[str] = None
    message: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    results: Optional[Dict[str, Any]] = None
    step_results: Optional[Dict[str, Any]] = None


@router.post("/status", status_code=status.HTTP_200_OK)
async def status_webhook(
    request: Request,
    payload: WebhookPayload = Body(...)
):
    """
    Receive status update from orchestrator.
    
    The orchestrator calls this endpoint whenever a workflow progresses,
    completes, or fails.
    """
    status_service = request.app.state.request_status_service
    request_id = payload.request_id
    
    if not request_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing request_id in payload"
        )
        
    logger.info(f"Received status webhook for request {request_id}: {payload.status}")
    
    # Map payload to database update arguments
    request_status = payload.status
    workflow_name = payload.workflow_name
    current_step = payload.current_step
    completed_steps = payload.completed_steps
    error_message = payload.error_message or payload.message

    # Infer status if missing (e.g., from OrchestratorCompletedEvent or OrchestratorFailedEvent)
    if not request_status:
        if payload.results or payload.step_results:
            request_status = RequestStatus.COMPLETED
        elif payload.failed_step or payload.error_message:
            request_status = RequestStatus.FAILED
        elif current_step:
            request_status = RequestStatus.IN_PROGRESS
        else:
            request_status = RequestStatus.PENDING
    
    # Handle completion results (e.g., extracting snapshot_id)
    snapshot_id = None
    results = payload.results or payload.step_results
    if results and isinstance(results, dict):
        # The orchestrator completed event often has results under 'archive_generation' or 'metadata_extraction'
        archive_results = results.get("archive_generation")
        if archive_results and isinstance(archive_results, dict):
            snapshot_id = archive_results.get("snapshot_id")
        
        # Fallback to checking results directly if it's flattened
        if not snapshot_id:
            snapshot_id = results.get("snapshot_id")

    # Update the database
    success = status_service.update_status(
        request_id=request_id,
        status=request_status,
        workflow_name=workflow_name,
        current_step=current_step,
        completed_steps=completed_steps,
        error_message=error_message,
        snapshot_id=snapshot_id
    )
    
    if not success:
        logger.error(f"Failed to update status in DB for request {request_id}")
        # We still return 200 to acknowledge receipt of webhook,
        # but log the internal failure.
    
    return {"status": "accepted"}
