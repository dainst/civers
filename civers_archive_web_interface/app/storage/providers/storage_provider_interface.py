"""
Abstract base class for storage providers.

This module defines the StorageProvider interface that all storage 
implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, IO
from pathlib import Path

from ...models.url import ArchivedUrl
from ...models.snapshot import Snapshot


class StorageProviderInterface(ABC):
    """
    Abstract base class for storage providers.
    
    Storage providers handle the backend-specific logic for discovering
    and accessing archived URLs and snapshots from different storage systems
    (filesystem, S3, database, etc.).
    """

    @abstractmethod
    def get_all_urls(self) -> Dict[str, ArchivedUrl]:
        """
        Get all archived URLs from storage.
        
        Returns:
            Dictionary mapping url_id to ArchivedUrl objects
            
        Raises:
            StorageError: If storage operation fails
        """
        pass

    @abstractmethod
    def get_url_by_id(self, url_id: str) -> Optional[ArchivedUrl]:
        """
        Get a specific archived URL by its ID.
        
        Args:
            url_id: The URL identifier
            
        Returns:
            ArchivedUrl object if found, None otherwise
            
        Raises:
            StorageError: If storage operation fails
        """
        pass

    @abstractmethod
    def get_snapshot_by_id(self, snapshot_id: str) -> Optional[Snapshot]:
        """
        Get a specific snapshot by its ID.
        
        Args:
            snapshot_id: The snapshot identifier
            
        Returns:
            Snapshot object if found, None otherwise
            
        Raises:
            StorageError: If storage operation fails
        """
        pass

    @abstractmethod
    def get_artifact_stream(self, snapshot_id: str, artifact_type: str) -> Optional[IO]:
        """
        Get a stream to a specific artifact file.
        
        Args:
            snapshot_id: The snapshot identifier
            artifact_type: Type of artifact (e.g., 'archive.wacz', 'screenshot.png')
            
        Returns:
            File-like object stream if found, None otherwise.
            The caller is responsible for closing the returned stream,
            e.g. by using it as a context manager or in a finally block.
            
        Raises:
            StorageError: If storage operation fails
        """
        pass

    @abstractmethod
    def artifact_exists(self, snapshot_id: str, artifact_type: str) -> bool:
        """
        Check if a specific artifact exists.
        
        Args:
            snapshot_id: The snapshot identifier  
            artifact_type: Type of artifact (e.g., 'archive.wacz', 'screenshot.png')
            
        Returns:
            True if artifact exists, False otherwise
            
        Raises:
            StorageError: If storage operation fails
        """
        pass

    @abstractmethod
    def get_artifact_path(self, snapshot_id: str, artifact_type: str) -> Optional[Path]:
        """
        Get the path to a specific artifact file.

        Note: This method may not be supported by all providers (e.g., S3).

        Args:
            snapshot_id: The snapshot identifier
            artifact_type: Type of artifact (e.g., 'archive.wacz', 'screenshot.png')

        Returns:
            Path to artifact file if supported and exists, None otherwise

        Raises:
            NotImplementedError: If provider doesn't support file paths
            StorageError: If storage operation fails
        """
        pass

    @abstractmethod
    def create_snapshot(
        self,
        url: str,
        request_id: str,
        files: Dict[str, IO],
        allow_existing: bool = False
    ) -> Snapshot:
        """
        Create a new snapshot with uploaded files.

        Stores uploaded archive files in structured directory and creates
        a snapshot record. Supports idempotent operations to add files to
        existing snapshots.

        Args:
            url: The URL being archived (e.g., 'https://example.com/page')
            request_id: Unique request identifier (used in snapshot_id generation)
            files: Dictionary mapping artifact filenames to file streams
                   (e.g., {'archive.wacz': stream, 'metadata.json': stream})
            allow_existing: If True, allow adding files to existing snapshot (default: False)

        Returns:
            Snapshot object representing the created/updated snapshot

        Raises:
            ValidationError: If URL is invalid, files are invalid, or snapshot already exists
                           (when allow_existing=False)
            StorageError: If storage operation fails

        Examples:
            >>> from io import BytesIO
            >>> files = {
            ...     'archive.wacz': BytesIO(b'wacz content'),
            ...     'screenshot.png': BytesIO(b'png content'),
            ...     'metadata.json': BytesIO(b'{"url": "https://example.com"}')
            ... }
            >>> snapshot = provider.create_snapshot(
            ...     url='https://example.com/page',
            ...     request_id='abc123',
            ...     files=files
            ... )
            >>> print(snapshot.snapshot_id)
            'req_abc123_20250112_143000'
        """
        pass


class StorageError(Exception):
    """Exception raised for storage-related errors."""
    pass


class StorageTimeoutError(StorageError):
    """Exception raised when storage operations timeout."""
    pass


class StoragePermissionError(StorageError):
    """Exception raised for storage permission errors."""
    pass