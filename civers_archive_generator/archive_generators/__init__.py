from abc import ABC, abstractmethod
from typing import List

# Import result types first (no circular dependencies since they're pure dataclasses)
from .archive_result import ArchiveResult, ArtifactResult, ArtifactStatus


class ArchiveGeneratorStrategyInterface(ABC):
    """Interface for archive generation strategies."""

    # List of artifact types this generator is capable of producing
    # Should be overridden by subclasses
    CAPABILITIES: List[str] = []

    @abstractmethod
    async def generate_archive(
        self, 
        url: str, 
        output_folder: str, 
        requested_artifacts: List[str]
    ) -> List[ArtifactResult]:
        """
        Generate specified archive artifacts for the given URL into the output folder.
        
        Args:
            url: The URL to archive
            output_folder: Path to the directory where artifacts should be saved
            requested_artifacts: List of artifact names to generate (subset of CAPABILITIES)
            
        Returns:
            List[ArtifactResult]: List of results for each generated artifact
            
        Raises:
            Exception: If archive generation fails catastrophically
        """
        pass

# Import factory class at the end to avoid circular imports
from .archive_generator_factory import ArchiveGeneratorFactory  # noqa: E402

__all__ = [
    'ArchiveGeneratorStrategyInterface',
    'ArchiveGeneratorFactory',
    'ArchiveResult',
    'ArtifactResult',
    'ArtifactStatus'
]