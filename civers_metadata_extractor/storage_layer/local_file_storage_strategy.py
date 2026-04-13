"""
Local File Storage Strategy Implementation.

Provides local filesystem storage for metadata JSON files.
This is the default, always-available storage backend.
"""

import json
import os
from typing import Any

import aiofiles  # type: ignore[import-untyped]
import aiofiles.os  # type: ignore[import-untyped]

from configs.logging_config import get_logger

from .storage_strategy import StorageResult, StorageStrategy


class LocalFileStorageStrategy(StorageStrategy):
    """
    Local filesystem storage strategy.

    Stores metadata as JSON files in a configurable local directory.
    This strategy is always available (no external dependencies) and
    serves as the default fallback storage backend.

    Attributes:
        base_path: Base directory for storing metadata files
        create_subdirectories: Whether to create subdirectories if needed
        logger: Logger instance for this strategy

    Example:
        >>> strategy = LocalFileStorageStrategy(base_path="output/metadata")
        >>> result = await strategy.store_metadata(
        ...     data={"test": "data"},
        ...     request_id="req_123",
        ...     url="https://example.com",
        ...     filename="metadata_test_req_123.json"
        ... )
        >>> print(result.success)
        True
        >>> print(result.storage_location)
        'output/metadata/metadata_test_req_123.json'
    """

    def __init__(self, base_path: str = "output/metadata", create_subdirectories: bool = True):
        """
        Initialize local file storage strategy.

        Args:
            base_path: Directory path where metadata files will be stored
            create_subdirectories: If True, creates base_path if it doesn't exist
        """
        self.base_path = base_path
        self.create_subdirectories = create_subdirectories
        self.logger = get_logger(__name__)

    async def store_metadata(
        self, data: dict[str, Any], request_id: str, url: str, filename: str
    ) -> StorageResult:
        """
        Store metadata to local filesystem as JSON file.

        Creates the base directory if it doesn't exist (when create_subdirectories=True),
        writes the metadata dictionary as formatted JSON, and returns the result.

        Args:
            data: Metadata dictionary to serialize and store
            request_id: Request ID for logging and tracking
            url: Original URL (not used by local storage, but part of interface)
            filename: Name for the JSON file

        Returns:
            StorageResult with success=True and filepath on success,
            or success=False with error message on failure
        """
        try:
            # Ensure output directory exists
            if self.create_subdirectories:
                await aiofiles.os.makedirs(self.base_path, exist_ok=True)

            # Generate full filepath
            filepath = os.path.join(self.base_path, filename)

            # Serialize metadata to JSON
            json_content = json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
                default=str,  # Handle non-serializable objects (dates, etc.)
            )

            # Write JSON file asynchronously
            async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
                await f.write(json_content)

            # Calculate file size
            file_size = len(json_content.encode("utf-8"))

            self.logger.info(f"✅ Stored metadata locally: {filepath} ({file_size} bytes)")

            return StorageResult(
                success=True,
                storage_type="local_file",
                storage_location=filepath,
                metadata={
                    "filepath": filepath,
                    "size_bytes": file_size,
                    "base_path": self.base_path,
                    "filename": filename,
                },
            )

        except OSError as e:
            # Filesystem errors (permissions, disk full, etc.)
            error_msg = f"Filesystem error: {e}"
            self.logger.error(f"❌ Failed to store metadata locally: {error_msg}")
            return StorageResult(success=False, storage_type="local_file", error_message=error_msg)

        except Exception as e:
            # Catch-all for unexpected errors
            error_msg = f"Unexpected error: {e}"
            self.logger.error(f"❌ Failed to store metadata locally: {error_msg}")
            return StorageResult(success=False, storage_type="local_file", error_message=error_msg)

    def get_storage_type(self) -> str:
        """
        Return the storage strategy type identifier.

        Returns:
            "local_file" - identifier for this storage backend
        """
        return "local_file"

    async def is_available(self) -> bool:
        """
        Check if local file storage is available.

        Tests whether the base directory can be created and is writable.
        This is typically always True unless there are permission issues.

        Returns:
            True if directory is accessible and writable, False otherwise
        """
        try:
            # Try to create the directory
            await aiofiles.os.makedirs(self.base_path, exist_ok=True)

            # Check if directory is writable by testing a temporary file
            test_file = os.path.join(self.base_path, ".storage_test")
            try:
                async with aiofiles.open(test_file, "w") as f:
                    await f.write("test")
                # Clean up test file
                await aiofiles.os.remove(test_file)
                return True
            except OSError:
                return False

        except OSError as e:
            self.logger.warning(f"Local file storage not available: {e}")
            return False
        except Exception as e:
            self.logger.warning(f"Local file storage availability check failed: {e}")
            return False
