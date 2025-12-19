"""
Storage service layer for centralized storage operations and caching.

This module provides the StorageService class that acts as the main interface
between APIs and storage providers, with centralized caching and business logic.
"""

import logging
import time
from typing import Dict, Optional, IO
from pathlib import Path

from ..models.url import ArchivedUrl
from ..models.snapshot import Snapshot
from .providers.storage_provider_interface import StorageProviderInterface, StorageError

logger = logging.getLogger(__name__)


class StorageService:
    """
    Centralized storage service with caching and business logic.
    
    This service provides the main interface for all storage operations,
    abstracting away the specific storage provider implementation and
    providing centralized caching with TTL support.
    """

    def __init__(self, provider: StorageProviderInterface, cache_ttl_seconds: int = 60):
        """
        Initialize storage service.
        
        Args:
            provider: Storage provider implementation
            cache_ttl_seconds: Cache TTL in seconds (0 to disable caching)
        """
        self.provider = provider
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cached_urls: Optional[Dict[str, ArchivedUrl]] = None
        self._cache_timestamp = 0.0
        
    def _is_cache_expired(self) -> bool:
        """Check if cache has expired based on TTL."""
        if self.cache_ttl_seconds <= 0:
            return True  # Caching disabled
        return time.time() - self._cache_timestamp > self.cache_ttl_seconds
    
    def _refresh_cache(self) -> Dict[str, ArchivedUrl]:
        """Refresh the URL cache from provider."""
        try:
            # Track cache operation timing separately from request timing
            cache_start_time = time.time()
            logger.debug("Refreshing storage cache from provider")

            self._cached_urls = self.provider.get_all_urls()
            self._cache_timestamp = time.time()

            # Log cache operation timing separately
            cache_duration_ms = round((self._cache_timestamp - cache_start_time) * 1000, 2)

            if self.cache_ttl_seconds > 0:
                logger.debug(f"Storage cache refreshed (TTL: {self.cache_ttl_seconds}s, URLs: {len(self._cached_urls)}, cache_time_ms: {cache_duration_ms})")
            else:
                logger.debug(f"Storage cache disabled (URLs: {len(self._cached_urls)}, cache_time_ms: {cache_duration_ms})")

            return self._cached_urls

        except Exception as e:
            logger.error(f"Failed to refresh storage cache: {e}")
            raise StorageError(f"Cache refresh failed: {str(e)}") from e
    
    def clear_cache(self) -> None:
        """Clear the cache manually and reset timestamp."""
        self._cached_urls = None
        self._cache_timestamp = 0.0
        logger.debug("Storage cache manually cleared")
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics for monitoring."""
        current_time = time.time()
        cache_age = current_time - self._cache_timestamp
        
        return {
            "cache_age_seconds": round(cache_age, 2),
            "ttl_seconds": self.cache_ttl_seconds,
            "cache_expired": self._is_cache_expired(),
            "cache_disabled": self.cache_ttl_seconds <= 0,
            "cached_urls_count": len(self._cached_urls) if self._cached_urls else 0,
            "last_refresh_timestamp": self._cache_timestamp
        }
    
    def get_all_urls(self) -> Dict[str, ArchivedUrl]:
        """
        Get all archived URLs with caching.
        
        Returns:
            Dictionary mapping url_id to ArchivedUrl objects
            
        Raises:
            StorageError: If storage operation fails
        """
        try:
            # Check if cache needs refresh
            if self._cached_urls is None or self._is_cache_expired():
                return self._refresh_cache()
            
            return self._cached_urls
            
        except Exception as e:
            logger.error(f"Error getting all URLs: {e}")
            raise StorageError(f"Failed to get all URLs: {str(e)}") from e
    
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
        try:
            # Get from cache first
            all_urls = self.get_all_urls()
            return all_urls.get(url_id)
            
        except Exception as e:
            logger.error(f"Error getting URL {url_id}: {e}")
            raise StorageError(f"Failed to get URL {url_id}: {str(e)}") from e
    
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
        try:
            # For snapshot lookups, delegate to provider as it may be more efficient
            # than scanning all cached URLs
            return self.provider.get_snapshot_by_id(snapshot_id)
            
        except Exception as e:
            logger.error(f"Error getting snapshot {snapshot_id}: {e}")
            raise StorageError(f"Failed to get snapshot {snapshot_id}: {str(e)}") from e
    
    def find_url_by_original_url(self, original_url: str) -> Optional[ArchivedUrl]:
        """
        Find an archived URL by its original URL value.
        
        Args:
            original_url: The original URL to search for
            
        Returns:
            ArchivedUrl object if found, None otherwise
            
        Raises:
            StorageError: If storage operation fails
        """
        try:
            # Get all URLs and find the one with matching original URL
            all_urls = self.get_all_urls()
            
            for _, archived_url in all_urls.items():
                #TODO: improve the search to avoid partial matches, may be strip url parameters in both variables
                archived_original_url = str(archived_url.original_url)
                if archived_original_url in original_url:
                    return archived_url
                    
            return None
            
        except Exception as e:
            logger.error(f"Error finding URL by original URL {original_url}: {e}")
            raise StorageError(f"Failed to find URL by original URL {original_url}: {str(e)}") from e
    
    def get_snapshots_for_url(self, url_id: str) -> list[Snapshot]:
        """
        Get all snapshots for a specific URL.
        
        Args:
            url_id: The URL identifier
            
        Returns:
            List of Snapshot objects for the URL
            
        Raises:
            StorageError: If storage operation fails
        """
        try:
            archived_url = self.get_url_by_id(url_id)
            return archived_url.snapshots if archived_url else []
            
        except Exception as e:
            logger.error(f"Error getting snapshots for URL {url_id}: {e}")
            raise StorageError(f"Failed to get snapshots for URL {url_id}: {str(e)}") from e
    
    def get_artifact_stream(self, snapshot_id: str, artifact_type: str) -> Optional[IO]:
        """
        Get a stream to a specific artifact file.
        
        Args:
            snapshot_id: The snapshot identifier
            artifact_type: Type of artifact (e.g., 'archive.wacz', 'screenshot.png')
            
        Returns:
            File-like object stream if found, None otherwise
            
        Raises:
            StorageError: If storage operation fails
        """
        try:
            return self.provider.get_artifact_stream(snapshot_id, artifact_type)
            
        except Exception as e:
            logger.error(f"Error getting artifact stream {snapshot_id}/{artifact_type}: {e}")
            raise StorageError(f"Failed to get artifact stream: {str(e)}") from e
    
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
        try:
            return self.provider.artifact_exists(snapshot_id, artifact_type)
            
        except Exception as e:
            logger.error(f"Error checking artifact existence {snapshot_id}/{artifact_type}: {e}")
            raise StorageError(f"Failed to check artifact existence: {str(e)}") from e
    
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
        try:
            return self.provider.get_artifact_path(snapshot_id, artifact_type)

        except Exception as e:
            logger.error(f"Error getting artifact path {snapshot_id}/{artifact_type}: {e}")
            raise StorageError(f"Failed to get artifact path: {str(e)}") from e

    def create_snapshot(
        self,
        url: str,
        request_id: str,
        files: Dict[str, IO],
        allow_existing: bool = False
    ) -> Snapshot:
        """
        Create a new snapshot with uploaded files.

        Delegates to the storage provider to store files and invalidates
        the cache to ensure fresh data on next query.

        Args:
            url: The URL being archived (e.g., 'https://example.com/page')
            request_id: Unique request identifier (used in snapshot_id generation)
            files: Dictionary mapping artifact filenames to file streams
                   (e.g., {'archive.wacz': stream, 'metadata.json': stream})
            allow_existing: If True, allow adding files to existing snapshot (default: False)

        Returns:
            Snapshot object representing the created/updated snapshot

        Raises:
            ValidationError: If URL is invalid, files invalid, or snapshot exists (when allow_existing=False)
            StorageError: If storage operation fails

        Examples:
            >>> from io import BytesIO
            >>> files = {
            ...     'archive.wacz': BytesIO(b'wacz content'),
            ...     'metadata.json': BytesIO(b'{"url": "https://example.com"}')
            ... }
            >>> snapshot = storage_service.create_snapshot(
            ...     url='https://example.com/page',
            ...     request_id='abc123',
            ...     files=files
            ... )
        """
        try:
            logger.info(
                f"Creating snapshot via service for URL '{url}' "
                f"(request_id={request_id}, allow_existing={allow_existing})"
            )

            # Delegate to provider
            snapshot = self.provider.create_snapshot(
                url=url,
                request_id=request_id,
                files=files,
                allow_existing=allow_existing
            )

            # Invalidate cache to ensure fresh data
            self.clear_cache()

            logger.info(
                f"Successfully created snapshot {snapshot.snapshot_id} with "
                f"{len(snapshot.available_artifacts)} artifacts"
            )

            return snapshot

        except Exception as e:
            logger.error(f"Error creating snapshot for URL '{url}': {e}")
            # Re-raise as-is (provider already wrapped errors appropriately)
            raise