"""
Archive Request Status Service.

This service manages the lifecycle of archive requests, tracking their status
and recording updates from the orchestrator.
"""

import logging
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from ..database.sqlite_manager import SQLiteManager
from ..constants import RequestStatus, ALLOWED_REQUEST_STATUS_FIELDS

logger = logging.getLogger(__name__)


class RequestStatusService:
    """
    Service for tracking archive request status in the database.
    
    This service provides CRUD operations for the 'request_status' table,
    allowing tracking of requests from submission to completion.
    """

    def __init__(self, db: SQLiteManager):
        """
        Initialize the request status service.
        
        Args:
            db: SQLite database manager
        """
        self.db = db

    def create_request(
        self,
        request_id: str,
        url: str,
        domain: str,
        callback_url: Optional[str] = None
    ) -> bool:
        """
        Create a new archive request record with 'pending' status.
        
        Args:
            request_id: Unique request identifier
            url: URL to be archived
            domain: Domain pattern selected for archiving
            callback_url: Webhook URL for status updates
            
        Returns:
            bool: True if created successfully, False otherwise
        """
        try:
            query = """
            INSERT INTO request_status (
                request_id, status, url, domain, callback_url, 
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            now = datetime.now(timezone.utc).isoformat()
            self.db.execute_query(query, (
                request_id, RequestStatus.PENDING, url, domain, callback_url, now, now
            ))
            logger.info(f"Created request status record for {request_id} (pending)")
            return True
        except Exception as e:
            logger.error(f"Failed to create request status record: {e}")
            return False

    def update_status(
        self,
        request_id: str,
        status: str,
        workflow_name: Optional[str] = None,
        current_step: Optional[str] = None,
        completed_steps: Optional[List[str]] = None,
        workflow_steps: Optional[List[str]] = None,
        error_message: Optional[str] = None,
        snapshot_id: Optional[str] = None
    ) -> bool:
        """
        Update the status of an existing archive request.
        
        Uses allowlisted field names to prevent SQL injection.
        
        Args:
            request_id: Unique request identifier
            status: New status (pending, in_progress, completed, failed)
            workflow_name: Workflow being executed
            current_step: Currently executing workflow step
            completed_steps: List of completed step names
            error_message: Error message if status is 'failed'
            snapshot_id: snapshot_id if status is 'completed'
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            # Build update fields using allowlist approach for security
            update_values: Dict[str, Any] = {
                "status": status,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if workflow_name is not None:
                update_values["workflow_name"] = workflow_name
                
            if current_step is not None:
                update_values["current_step"] = current_step
                
            if completed_steps is not None:
                update_values["completed_steps"] = json.dumps(completed_steps)

            if workflow_steps is not None:
                update_values["workflow_steps"] = json.dumps(workflow_steps)

            if error_message is not None:
                update_values["error_message"] = error_message
                
            if snapshot_id is not None:
                update_values["snapshot_id"] = snapshot_id
            
            # Build query using only allowlisted field names
            fields = []
            params = []
            for field_name, value in update_values.items():
                # Security: Only allow explicitly whitelisted field names
                if field_name in ALLOWED_REQUEST_STATUS_FIELDS:
                    fields.append(f"{field_name} = ?")
                    params.append(value)
                else:
                    logger.warning(f"Attempted to update non-allowlisted field: {field_name}")
            
            if not fields:
                logger.error("No valid fields to update")
                return False
            
            params.append(request_id)
            query = f"UPDATE request_status SET {', '.join(fields)} WHERE request_id = ?"
            
            self.db.execute_query(query, tuple(params))
            logger.debug(f"Updated request {request_id} to status {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to update request status for {request_id}: {e}")
            return False

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an archive request record by request_id.
        
        Args:
            request_id: Unique request identifier
            
        Returns:
            Dict containing record data or None if not found
        """
        try:
            query = "SELECT * FROM request_status WHERE request_id = ?"
            result = self.db.fetch_one(query, (request_id,))
            
            if result:
                # Parse JSON fields
                if result.get('completed_steps'):
                    try:
                        result['completed_steps'] = json.loads(result['completed_steps'])
                    except json.JSONDecodeError:
                        result['completed_steps'] = []
                if result.get('workflow_steps'):
                    try:
                        result['workflow_steps'] = json.loads(result['workflow_steps'])
                    except json.JSONDecodeError:
                        result['workflow_steps'] = []
                return result
            return None
        except Exception as e:
            logger.error(f"Failed to get request record {request_id}: {e}")
            return None

    def get_all_requests(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get all archive requests with pagination.
        
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of records as dicts
        """
        try:
            query = "SELECT * FROM request_status ORDER BY created_at DESC LIMIT ? OFFSET ?"
            results = self.db.fetch_all(query, (limit, offset))
            
            for result in results:
                if result.get('completed_steps'):
                    try:
                        result['completed_steps'] = json.loads(result['completed_steps'])
                    except json.JSONDecodeError:
                        result['completed_steps'] = []
            return results
        except Exception as e:
            logger.error(f"Failed to list request records: {e}")
            return []

    def delete_request(self, request_id: str) -> bool:
        """
        Delete an archive request record.
        
        Args:
            request_id: Unique request identifier
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            query = "DELETE FROM request_status WHERE request_id = ?"
            self.db.execute_query(query, (request_id,))
            return True
        except Exception as e:
            logger.error(f"Failed to delete request record {request_id}: {e}")
            return False
