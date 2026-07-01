"""Callback Service for CiVers Orchestrator.

Handles sending HTTP POST notifications to external systems via callback URLs.
This allows systems like the web interface to receive real-time updates without
polling or direct Kafka consumption.
"""

import asyncio
import ipaddress
from typing import Any
from urllib.parse import urlparse

import httpx

from configs.logging_config import get_logger

logger = get_logger(__name__)

# Compiled once at import time
_ALLOWED_SCHEMES = {"http", "https"}
_PRIVATE_IP_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_safe_callback_url(url: str) -> bool:
    """Return True only if url is http/https and not targeting a private address."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_SCHEMES:
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # Reject raw IP addresses in private/link-local ranges
        try:
            addr = ipaddress.ip_address(hostname)
            return not any(addr in net for net in _PRIVATE_IP_NETWORKS)
        except ValueError:
            # hostname is a domain name — allow it
            return True
    except Exception:
        return False


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
        payload: dict[str, Any],
        request_id: str | None = None
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

        if not _is_safe_callback_url(callback_url):
            logger.error(
                f"❌ Blocked callback to unsafe URL '{callback_url}' "
                f"(request: {request_id or 'unknown'}). "
                "Only http/https to public hosts are allowed."
            )
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
