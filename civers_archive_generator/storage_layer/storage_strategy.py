"""The storage backend interface and its result models."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from domain.artifacts import ArchiveBundle  # noqa: F401  (used in annotations)


@dataclass
class StorageResult:
    """Publication result for one backend, including its name and output location."""
    success: bool
    storage_type: str
    storage_location: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass 
class MultiStorageResult:
    """Publication results. overall_success is true if at least one backend succeeded."""
    overall_success: bool
    results: List[StorageResult]
    
    def get_result_by_type(self, storage_type: str) -> Optional[StorageResult]:
        """Return the result for one backend, or None if it did not run."""
        for result in self.results:
            if result.storage_type == storage_type:
                return result
        return None
    
    def snapshot_id(self) -> Optional[str]:
        """Return the successful CIVERS API snapshot ID, or None for local fallback."""
        result = self.get_result_by_type("civers_rest_api")
        return result.storage_location if result and result.success else None

    def get_successful_backends(self) -> List[str]:
        """Return the storage types that succeeded."""
        return [r.storage_type for r in self.results if r.success]
    
    def get_failed_backends(self) -> List[str]:
        """Return the storage types that failed."""
        return [r.storage_type for r in self.results if not r.success]


class StorageStrategy(ABC):
    """Storage backend interface. Implement store_artifacts to publish a bundle."""

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "StorageStrategy":
        """Instantiate this strategy from a backend config dict."""
        return cls(**config)

    @abstractmethod
    async def store_artifacts(self, bundle: "ArchiveBundle") -> StorageResult:
        """Publish selected bundle files and return a StorageResult.

        Return success=False for upload failures.
        """
        pass
