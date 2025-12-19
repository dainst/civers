"""
CIVERS REST API Storage Strategy Implementation.

Provides cloud storage via the CIVERS archive API for metadata uploads.
This strategy requires the httpx library for HTTP operations.
"""

import json
from typing import Dict, Any, Optional
from configs.logging_config import get_logger
from .storage_strategy import StorageStrategy, StorageResult

# Conditional import for httpx
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class CiversRestApiStorageStrategy(StorageStrategy):
    """
    CIVERS REST API storage strategy.
    
    Uploads metadata to the CIVERS archive storage service via HTTP POST.
    Supports authentication, retry logic, and health checking.
    
    Requires httpx library: install with `uv sync --extra http`
    
    Attributes:
        upload_url: API endpoint for uploading metadata
        timeout_seconds: Request timeout in seconds
        retry_attempts: Number of retry attempts on failure
        verify_ssl: Whether to verify SSL certificates
        auth_config: Authentication configuration (type, token/key)
        logger: Logger instance for this strategy
    
    Example:
        >>> strategy = CiversRestApiStorageStrategy(
        ...     upload_url="http://localhost:8000/api/upload",
        ...     auth={"enabled": True, "type": "bearer", "token": "abc123"}
        ... )
        >>> result = await strategy.store_metadata(
        ...     data={"test": "data"},
        ...     request_id="req_123",
        ...     url="https://example.com",
        ...     filename="metadata.json"
        ... )
        >>> print(result.success)
        True
        >>> print(result.storage_location)
        'snapshot_req_123_20251208'
    """
    
    def __init__(
        self,
        upload_url: str,
        timeout_seconds: int = 30,
        retry_attempts: int = 3,
        verify_ssl: bool = True,
        auth: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize CIVERS REST API storage strategy.
        
        Args:
            upload_url: Full URL to the upload API endpoint
            timeout_seconds: Request timeout (default: 30)
            retry_attempts: Number of retry attempts (default: 3)
            verify_ssl: Verify SSL certificates (default: True)
            auth: Authentication configuration dict with keys:
                  - enabled (bool): Whether auth is enabled
                  - type (str): "bearer" or "api_key"
                  - token (str): Token/key value (if enabled)
        
        Raises:
            ImportError: If httpx library is not installed
        """
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx library is required for CIVERS REST API storage. "
                "Install with: uv sync --extra http"
            )
        
        self.upload_url = upload_url
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.verify_ssl = verify_ssl
        self.auth_config = auth or {"enabled": False}
        self.logger = get_logger(__name__)
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers based on configuration.
        
        Returns:
            Dictionary of headers for authentication, or empty dict if disabled
        """
        if not self.auth_config.get("enabled", False):
            return {}
        
        auth_type = self.auth_config.get("type", "bearer")
        token = self.auth_config.get("token", "")
        
        if auth_type == "bearer":
            return {"Authorization": f"Bearer {token}"}
        elif auth_type == "api_key":
            return {"X-API-Key": token}
        else:
            self.logger.warning(f"Unknown auth type: {auth_type}")
            return {}
    
    async def store_metadata(
        self,
        data: Dict[str, Any],
        request_id: str,
        url: str,
        filename: str
    ) -> StorageResult:
        """
        Upload metadata to CIVERS REST API.
        
        Creates multipart form data with the metadata JSON file and
        sends it to the configured upload endpoint with retries.
        
        Args:
            data: Metadata dictionary to upload
            request_id: Request ID for tracking
            url: Original source URL (required by CIVERS API)
            filename: Filename for the metadata (used for multipart form)
            
        Returns:
            StorageResult with success=True and snapshot_id on success,
            or success=False with error message on failure
        """
        # Convert metadata to JSON bytes
        try:
            json_content = json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
                default=str
            )
            json_bytes = json_content.encode('utf-8')
        except Exception as e:
            error_msg = f"Failed to serialize metadata to JSON: {e}"
            self.logger.error(f"❌ {error_msg}")
            return StorageResult(
                success=False,
                storage_type="civers_rest_api",
                error_message=error_msg
            )
        
        # Prepare form data
        form_data = {
            "url": url,
            "request_id": request_id,
            "allow_existing": "true"
        }
        
        # Prepare files
        files = {
            "files": ("metadata.json", json_bytes, "application/json")
        }
        
        # Prepare headers
        headers = self._get_auth_headers()
        
        # Attempt upload with retries
        last_error = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                self.logger.info(
                    f"📤 Uploading to CIVERS API (attempt {attempt}/{self.retry_attempts}): "
                    f"{request_id}"
                )
                
                async with httpx.AsyncClient(
                    timeout=self.timeout_seconds,
                    verify=self.verify_ssl
                ) as client:
                    response = await client.post(
                        self.upload_url,
                        data=form_data,
                        files=files,
                        headers=headers
                    )
                    
                    # Check response status
                    if response.status_code == 200:
                        # Parse response
                        try:
                            response_data = response.json()
                            snapshot_id = response_data.get("snapshot_id", request_id)
                            
                            self.logger.info(
                                f"✅ Uploaded to CIVERS API: snapshot_id={snapshot_id}"
                            )
                            
                            return StorageResult(
                                success=True,
                                storage_type="civers_rest_api",
                                storage_location=snapshot_id,
                                metadata={
                                    "snapshot_id": snapshot_id,
                                    "upload_url": self.upload_url,
                                    "source_url": url,
                                    "size_bytes": len(json_bytes),
                                    "attempt": attempt
                                }
                            )
                        except Exception as e:
                            # Response was 200 but couldn't parse JSON
                            self.logger.warning(
                                f"API returned 200 but couldn't parse response: {e}"
                            )
                            # Still consider it a success
                            return StorageResult(
                                success=True,
                                storage_type="civers_rest_api",
                                storage_location=request_id,
                                metadata={
                                    "snapshot_id": request_id,
                                    "upload_url": self.upload_url,
                                    "source_url": url,
                                    "size_bytes": len(json_bytes),
                                    "attempt": attempt,
                                    "parse_error": str(e)
                                }
                            )
                    else:
                        # HTTP error status
                        error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                        self.logger.warning(f"Upload attempt {attempt} failed: {error_msg}")
                        last_error = error_msg
                        
                        # Don't retry on client errors (4xx)
                        if 400 <= response.status_code < 500:
                            break
                        
            except httpx.TimeoutException as e:
                error_msg = f"Request timeout after {self.timeout_seconds}s"
                self.logger.warning(f"Upload attempt {attempt} failed: {error_msg}")
                last_error = error_msg
                
            except httpx.ConnectError as e:
                error_msg = f"Connection failed: {e}"
                self.logger.warning(f"Upload attempt {attempt} failed: {error_msg}")
                last_error = error_msg
                
            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                self.logger.warning(f"Upload attempt {attempt} failed: {error_msg}")
                last_error = error_msg
        
        # All attempts failed
        final_error = f"All {self.retry_attempts} upload attempts failed. Last error: {last_error}"
        self.logger.error(f"❌ {final_error}")
        
        return StorageResult(
            success=False,
            storage_type="civers_rest_api",
            error_message=final_error,
            metadata={
                "upload_url": self.upload_url,
                "attempts": self.retry_attempts
            }
        )
    
    def get_storage_type(self) -> str:
        """
        Return the storage strategy type identifier.
        
        Returns:
            "civers_rest_api" - identifier for this storage backend
        """
        return "civers_rest_api"
    
    async def is_available(self) -> bool:
        """
        Check if CIVERS REST API is available.
        
        Sends an OPTIONS request to the upload endpoint to check if
        the API is reachable and responding. Uses a short timeout.
        
        Returns:
            True if API responds with status < 500, False otherwise
        """
        if not HTTPX_AVAILABLE:
            return False
        
        try:
            async with httpx.AsyncClient(
                timeout=5.0,  # Short timeout for health check
                verify=self.verify_ssl
            ) as client:
                response = await client.options(self.upload_url)
                # Consider API available if it responds with any status < 500
                return response.status_code < 500
                
        except httpx.TimeoutException:
            self.logger.warning("CIVERS API health check timed out")
            return False
        except httpx.ConnectError:
            self.logger.warning("CIVERS API health check connection failed")
            return False
        except Exception as e:
            self.logger.warning(f"CIVERS API health check failed: {e}")
            return False
