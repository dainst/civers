"""
CIVERS REST API Storage Strategy Implementation.

Provides cloud storage via the CIVERS archive API for metadata uploads.
This strategy requires the httpx library for HTTP operations.
"""

import json
from typing import Dict, Any, Optional, List
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
    
    async def store_artifacts(
        self,
        archive_path: str,
        request_id: str,
        url: str,
        artifact_files: Optional[List[str]] = None
    ) -> StorageResult:
        """
        Upload multiple archive artifact files to CIVERS REST API.
        
        This method uploads all archive files from an archive directory
        (or specific files) to the CIVERS API in a single request.
        
        Args:
            archive_path: Path to the archive directory containing artifacts
            request_id: Request ID for tracking
            url: Original source URL (required by CIVERS API)
            artifact_files: Optional list of specific files to upload.
                           If None, uploads all recognized artifact files.
        
        Supported artifact types:
            - archive.wacz: WACZ archive file
            - singlefile.html: SingleFile self-contained HTML
            - document.html: DOM snapshot HTML
            - screenshot.png: Screenshot image
            - metadata.json: Archive metadata
        
        Returns:
            StorageResult with success=True and snapshot_id on success,
            or success=False with error message on failure
        """
        import io
        from pathlib import Path
        
        archive_dir = Path(archive_path)
        
        # Define recognized artifact files and their content types
        ARTIFACT_TYPES = {
            "archive.wacz": "application/octet-stream",
            "singlefile.html": "text/html",
            "document.html": "text/html",
            "dom-snapshot.html": "text/html",  # DOM snapshot from Scoop
            "screenshot.png": "image/png",
            "archive_generator_metadata.json": "application/json",
        }
        
        # Filename mappings: local_name -> api_name
        # The API expects certain filenames that may differ from what the archive generator creates
        FILENAME_MAPPINGS = {
            "metadata.json": "archive_generator_metadata.json",  # Rename to distinguish from metadata extractor's metadata
        }
        
        # Find files to upload
        files_to_upload = []
        
        if artifact_files:
            # Use specified files
            for filename in artifact_files:
                file_path = archive_dir / filename
                if file_path.exists():
                    # Use mapped name for API if available
                    api_filename = FILENAME_MAPPINGS.get(filename, filename)
                    content_type = ARTIFACT_TYPES.get(api_filename, "application/octet-stream")
                    files_to_upload.append((api_filename, file_path, content_type))
                else:
                    self.logger.warning(f"Specified file not found: {file_path}")
        else:
            # Auto-discover artifact files
            if archive_dir.is_dir():
                # First check for direct matches
                for filename, content_type in ARTIFACT_TYPES.items():
                    file_path = archive_dir / filename
                    if file_path.exists():
                        files_to_upload.append((filename, file_path, content_type))
                
                # Then check for files that need mapping
                for local_name, api_name in FILENAME_MAPPINGS.items():
                    file_path = archive_dir / local_name
                    if file_path.exists() and api_name not in [f[0] for f in files_to_upload]:
                        content_type = ARTIFACT_TYPES.get(api_name, "text/html")
                        files_to_upload.append((api_name, file_path, content_type))
                        
            elif archive_dir.is_file():
                # Single file case
                filename = archive_dir.name
                api_filename = FILENAME_MAPPINGS.get(filename, filename)
                content_type = ARTIFACT_TYPES.get(api_filename, "application/octet-stream")
                files_to_upload.append((api_filename, archive_dir, content_type))
        
        if not files_to_upload:
            error_msg = f"No artifact files found in: {archive_path}"
            self.logger.error(f"❌ {error_msg}")
            return StorageResult(
                success=False,
                storage_type="civers_rest_api",
                error_message=error_msg
            )
        
        self.logger.info(
            f"📦 Uploading {len(files_to_upload)} artifact(s) to CIVERS API: "
            f"{[f[0] for f in files_to_upload]}"
        )
        
        # Prepare form data
        form_data = {
            "url": url,
            "request_id": request_id,
            "allow_existing": "true"
        }
        
        # Prepare files list for multipart upload
        file_tuples = []
        total_size = 0
        
        for filename, file_path, content_type in files_to_upload:
            try:
                file_content = file_path.read_bytes()
                total_size += len(file_content)
                file_tuples.append(
                    ("files", (filename, io.BytesIO(file_content), content_type))
                )
            except Exception as e:
                self.logger.warning(f"Failed to read {filename}: {e}")
        
        if not file_tuples:
            error_msg = "Failed to read any artifact files"
            self.logger.error(f"❌ {error_msg}")
            return StorageResult(
                success=False,
                storage_type="civers_rest_api",
                error_message=error_msg
            )
        
        # Prepare headers
        headers = self._get_auth_headers()
        
        # Attempt upload with retries
        last_error = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                self.logger.info(
                    f"📤 Uploading artifacts to CIVERS API (attempt {attempt}/{self.retry_attempts}): "
                    f"{request_id} ({total_size} bytes, {len(file_tuples)} files)"
                )
                
                async with httpx.AsyncClient(
                    timeout=self.timeout_seconds * 2,  # More time for larger uploads
                    verify=self.verify_ssl
                ) as client:
                    response = await client.post(
                        self.upload_url,
                        data=form_data,
                        files=file_tuples,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                            snapshot_id = response_data.get("snapshot_id", request_id)
                            artifacts_uploaded = response_data.get("artifacts_uploaded", [])
                            
                            self.logger.info(
                                f"✅ Uploaded {len(artifacts_uploaded)} artifact(s) to CIVERS API: "
                                f"snapshot_id={snapshot_id}"
                            )
                            
                            return StorageResult(
                                success=True,
                                storage_type="civers_rest_api",
                                storage_location=snapshot_id,
                                metadata={
                                    "snapshot_id": snapshot_id,
                                    "upload_url": self.upload_url,
                                    "source_url": url,
                                    "total_size_bytes": total_size,
                                    "files_uploaded": artifacts_uploaded,
                                    "attempt": attempt
                                }
                            )
                        except Exception as e:
                            # Response was 200 but couldn't parse JSON
                            self.logger.warning(
                                f"API returned 200 but couldn't parse response: {e}"
                            )
                            return StorageResult(
                                success=True,
                                storage_type="civers_rest_api",
                                storage_location=request_id,
                                metadata={
                                    "snapshot_id": request_id,
                                    "upload_url": self.upload_url,
                                    "source_url": url,
                                    "total_size_bytes": total_size,
                                    "attempt": attempt,
                                    "parse_error": str(e)
                                }
                            )
                    else:
                        error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                        self.logger.warning(f"Upload attempt {attempt} failed: {error_msg}")
                        last_error = error_msg
                        
                        if 400 <= response.status_code < 500:
                            break
                        
            except httpx.TimeoutException:
                error_msg = f"Request timeout after {self.timeout_seconds * 2}s"
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
                "attempts": self.retry_attempts,
                "files_attempted": [f[0] for f in files_to_upload]
            }
        )
