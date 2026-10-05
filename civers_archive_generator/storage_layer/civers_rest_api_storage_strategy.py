"""Upload selected capture files to the CIVERS archive API using httpx."""

import aiofiles

from typing import Dict, Any, Optional, List

from civers_common import ConfigurationError

from configs.logging_config import get_logger
from domain.artifacts import ArchiveBundle, ArtifactFile
from .storage_strategy import StorageStrategy, StorageResult

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class CiversRestApiStorageStrategy(StorageStrategy):
    """Upload selected files to the CIVERS archive API in one multipart request."""
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "CiversRestApiStorageStrategy":
        """Build the backend from its upload, retry and authentication settings."""
        return cls(
            upload_url=config["upload_url"],
            timeout_seconds=int(config.get("timeout_seconds", 30)),
            retry_attempts=int(config.get("retry_attempts", 3)),
            verify_ssl=config.get("verify_ssl", True),
            auth=config.get("auth"),
        )

    def __init__(
        self,
        upload_url: str,
        timeout_seconds: int = 30,
        retry_attempts: int = 3,
        verify_ssl: bool | str | None = True,
        auth: Optional[Dict[str, Any]] = None
    ):
        """Initialize the backend against an upload endpoint.

        Args:
            auth: ``{"enabled": bool, "type": "bearer" | "api_key", "token": str}``.

        Raises:
            ImportError: httpx is not installed.
        """
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx library is required for CIVERS REST API storage. "
                "Install with: uv sync --extra http"
            )
        
        self.upload_url = upload_url
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.auth_config = auth or {"enabled": False}
        verify_ssl = True if verify_ssl is None else verify_ssl
        auth_enabled = self.auth_config.get("enabled")
        auth_enabled = False if auth_enabled is None else auth_enabled
        # Parse string switches explicitly: bool("false") is True.
        true_values = {"true", "yes", "on", "1"}
        false_values = {"false", "no", "off", "0", ""}
        for name, value in (("verify_ssl", verify_ssl), ("auth.enabled", auth_enabled)):
            if not isinstance(value, (bool, str)) or str(value).strip().lower() not in true_values | false_values:
                raise ConfigurationError(f"storage.{name} must be a boolean; got {value!r}")
        self.verify_ssl = str(verify_ssl).strip().lower() in true_values
        self.auth_enabled = str(auth_enabled).strip().lower() in true_values
        self.logger = get_logger(__name__)

    def _get_auth_headers(self) -> Dict[str, str]:
        """Build authentication headers; raise ConfigurationError for a missing token."""
        if not self.auth_enabled:
            return {}

        auth_type = self.auth_config.get("type", "bearer")
        token = self.auth_config.get("token", "")
        if not token:
            raise ConfigurationError(
                "storage.auth is enabled but no 'token' is configured"
            )
        
        if auth_type == "bearer":
            return {"Authorization": f"Bearer {token}"}
        elif auth_type == "api_key":
            return {"X-API-Key": token}
        else:
            self.logger.warning(f"Unknown auth type: {auth_type}")
            return {}
    
    # Upload these filenames; leave logs and intermediate files local.
    PUBLISHABLE = {
        "archive.wacz",
        "archive.warc",
        "singlefile.html",
        "document.html",
        "dom-snapshot.html",
        "screenshot.png",
        "archive_generator_metadata.json",
    }

    @classmethod
    def _select(cls, bundle: ArchiveBundle) -> List[ArtifactFile]:
        """Select upload filenames from the bundle without scanning the folder."""
        return [f for f in bundle.files if f.name in cls.PUBLISHABLE]

    async def store_artifacts(self, bundle: ArchiveBundle) -> StorageResult:
        """Upload selected files and return their publication result.

        Authentication configuration errors may raise ConfigurationError.
        """
        import io

        url = bundle.url
        request_id = bundle.request_id
        files_to_upload = self._select(bundle)

        if not files_to_upload:
            error_msg = f"No artifact files found in: {bundle.root}"
            self.logger.error(f"❌ {error_msg}")
            return StorageResult(
                success=False,
                storage_type="civers_rest_api",
                error_message=error_msg
            )

        self.logger.info(
            f"📦 Uploading {len(files_to_upload)} artifact(s) to CIVERS API: "
            f"{[f.name for f in files_to_upload]}"
        )

        form_data = {
            "url": url,
            "request_id": request_id,
            "allow_existing": "true"
        }
        
        file_tuples = []
        total_size = 0
        
        for artifact in files_to_upload:
            try:
                # Read file contents without blocking other async tasks.
                async with aiofiles.open(artifact.path, "rb") as f:
                    file_content = await f.read()
                total_size += len(file_content)
                file_tuples.append(
                    ("files", (artifact.name, io.BytesIO(file_content), artifact.media_type))
                )
            except Exception as e:
                self.logger.warning(f"Failed to read {artifact.name}: {e}")
        
        if not file_tuples:
            error_msg = "Failed to read any artifact files"
            self.logger.error(f"❌ {error_msg}")
            return StorageResult(
                success=False,
                storage_type="civers_rest_api",
                error_message=error_msg
            )
        
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
                            # Accept HTTP 200 even if the response data cannot be read.
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
        
        final_error = f"All {self.retry_attempts} upload attempts failed. Last error: {last_error}"
        self.logger.error(f"❌ {final_error}")
        
        return StorageResult(
            success=False,
            storage_type="civers_rest_api",
            error_message=final_error,
            metadata={
                "upload_url": self.upload_url,
                "attempts": self.retry_attempts,
                "files_attempted": [artifact.name for artifact in files_to_upload]
            }
        )
