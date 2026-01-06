"""Callback Service for CiVers Orchestrator.

Handles sending HTTP POST notifications to external systems via callback URLs.
This allows systems like the web interface to receive real-time updates without
polling or direct Kafka consumption.
"""

import httpx
import asyncio
from typing import Any, Dict, Optional
from configs.logging_config import get_logger

logger = get_logger(__name__)

class CallbackService:
    """
    Service for sending asynchronous HTTP callbacks.
    
    Responsibilities:
    - Sending POST requests to registered callback URLs
    - Retrying on failure (optional)
    - Handling timeouts and logging results
    """

    def __init__(self, timeout: float = 5.0, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries

    async def send_callback(
        self, 
        callback_url: str, 
        payload: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> bool:
        """
        Send an asynchronous HTTP POST callback.
        
        Args:
            callback_url: The destination URL
            payload: The data to send as JSON
            request_id: Optional ID for logging
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not callback_url:
            return False

        req_info = f"Request: {request_id or 'unknown'}"
        logger.info(f"📤 Sending callback ({req_info}) to {callback_url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(callback_url, json=payload)
                    response.raise_for_status()
                    logger.debug(f"✅ Callback successful ({req_info}): HTTP {response.status_code}")
                    return True
                except httpx.HTTPStatusError as e:
                    logger.warning(
                        f"⚠️ Callback failed ({req_info}): HTTP {e.response.status_code} "
                        f"on attempt {attempt + 1}"
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️ Callback error ({req_info}): {str(e)} "
                        f"on attempt {attempt + 1}"
                    )
                
                if attempt < self.max_retries:
                    await asyncio.sleep(1 * (attempt + 1)) # Simple backoff

        logger.error(f"❌ Callback failed after {self.max_retries + 1} attempts for {request_id}")
        return False
