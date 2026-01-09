"""
Storage Strategy Interface and Result Models.

This module defines the abstract interface that all storage strategies must implement,
along with dataclasses for representing storage operation results.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StorageResult:
    """
    Result of a single storage operation.
    
    Represents the outcome of storing metadata to one storage backend.
    
    Attributes:
        success: Whether the storage operation succeeded
        storage_type: Backend identifier (e.g., "local_file", "civers_rest_api")
        storage_location: Where the data was stored (file path, URL, or resource ID)
        error_message: Error description if operation failed
        metadata: Additional information about the operation
        created_at: ISO format timestamp when operation completed
    """
    success: bool
    storage_type: str
    storage_location: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass 
class MultiStorageResult:
    """
    Aggregated result from multiple storage backends.
    
    When storing to multiple backends simultaneously, this class aggregates
    the individual results and provides helper methods to query the outcomes.
    
    Attributes:
        overall_success: True if AT LEAST ONE backend succeeded
        results: List of individual StorageResult for each backend
        primary_location: Primary storage location (usually local_file path)
    """
    overall_success: bool
    results: List[StorageResult]
    primary_location: Optional[str] = None
    
    def get_result_by_type(self, storage_type: str) -> Optional[StorageResult]:
        """
        Get result for a specific storage backend.
        
        Args:
            storage_type: Backend identifier to search for
            
        Returns:
            StorageResult for the specified backend, or None if not found
        """
        for result in self.results:
            if result.storage_type == storage_type:
                return result
        return None
    
    def get_successful_backends(self) -> List[str]:
        """
        Get list of storage types that succeeded.
        
        Returns:
            List of backend identifiers that completed successfully
        """
        return [r.storage_type for r in self.results if r.success]
    
    def get_failed_backends(self) -> List[str]:
        """
        Get list of storage types that failed.
        
        Returns:
            List of backend identifiers that failed
        """
        return [r.storage_type for r in self.results if not r.success]


class StorageStrategy(ABC):
    """
    Abstract base class for storage strategy implementations.
    
    All storage backends must implement this interface to be compatible
    with the StorageManager. The Strategy pattern allows swapping storage
    implementations without changing the service layer.
    
    Example:
        class MyCustomStrategy(StorageStrategy):
            async def store_metadata(self, data, request_id, url, filename):
                # Implementation
                return StorageResult(...)
            
            def get_storage_type(self):
                return "my_custom_backend"
            
            async def is_available(self):
                return True
    """
    
    @abstractmethod
    async def store_metadata(
        self,
        data: Dict[str, Any],
        request_id: str,
        url: str,
        filename: str
    ) -> StorageResult:
        """
        Store metadata JSON.
        
        This is the main operation that all storage strategies must implement.
        It should store the metadata dictionary to the backend and return
        a result indicating success or failure.
        
        Args:
            data: Metadata dictionary to store (will be serialized to JSON)
            request_id: Request ID for tracking and logging
            url: Original URL being processed (needed for some backends like CIVERS API)
            filename: Suggested filename for the metadata file
            
        Returns:
            StorageResult with success status, location, and any error details
            
        Raises:
            Should NOT raise exceptions - return StorageResult with success=False instead
        """
        pass
    
    @abstractmethod
    def get_storage_type(self) -> str:
        """
        Return the storage strategy type identifier.
        
        This should be a unique string identifying this storage backend.
        Examples: "local_file", "civers_rest_api", "s3", "azure_blob"
        
        Returns:
            Unique identifier for this storage strategy
        """
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if this storage backend is available and ready.
        
        This method should perform a quick health check to determine if
        the backend can be used. For example:
        - Local file: check if directory is writable
        - HTTP API: send OPTIONS request
        - S3: check credentials and bucket access
        
        Returns:
            True if backend is available and ready to use, False otherwise
            
        Note:
            This should be a fast check, not a full integration test.
            Timeout should be short (e.g., 5 seconds for network checks).
        """
        pass
