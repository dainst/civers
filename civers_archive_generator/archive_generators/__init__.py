# archive_generators/__init__.py
from abc import ABC, abstractmethod
from typing import Union

# Import result types first (no circular dependencies since they're pure dataclasses)
from .archive_result import ArchiveResult, ArtifactResult, ArtifactStatus


class ArchiveGeneratorStrategyInterface(ABC):
    """Interface for archive generation strategies."""

    @abstractmethod
    async def generate_archive(self, url: str, request_id: str) -> ArchiveResult:
        """
        Generate archive artifacts for the given URL.
        
        Args:
            url: The URL to archive
            request_id: Unique identifier for this request
            
        Returns:
            ArchiveResult: Structured result with success/failure status and artifact details
            
        Raises:
            Exception: If archive generation fails catastrophically
        """
        pass

# Import factory class
from .archive_generator_factory import ArchiveGeneratorFactory

__all__ = [
    'ArchiveGeneratorStrategyInterface',
    'ArchiveGeneratorFactory',
    'ArchiveResult',
    'ArtifactResult',
    'ArtifactStatus'
]