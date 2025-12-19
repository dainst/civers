# archive_generators/__init__.py
from abc import ABC, abstractmethod

class ArchiveGeneratorStrategyInterface(ABC):
    """Interface for archive generation strategies."""

    @abstractmethod
    async def generate_archive(self, url: str, request_id: str) -> str:
        """
        Generate archive artifacts for the given URL.
        
        Args:
            url: The URL to archive
            request_id: Unique identifier for this request
            
        Returns:
            str: Path to the created archive directory
            
        Raises:
            Exception: If archive generation fails
        """
        pass

# Import factory class
from .archive_generator_factory import ArchiveGeneratorFactory

__all__ = [
    'ArchiveGeneratorStrategyInterface',
    'ArchiveGeneratorFactory'
]