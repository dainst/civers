"""Archive generator interface and artifact results."""

from abc import ABC, abstractmethod
from typing import List

from .archive_result import ArtifactResult, ArtifactStatus


class ArchiveGeneratorStrategyInterface(ABC):
    """Interface for archive generation strategies."""

    # Artifact types supported by each implementation.
    CAPABILITIES: List[str] = []

    @abstractmethod
    async def generate_archive(
        self, 
        url: str, 
        output_folder: str, 
        requested_artifacts: List[str]
    ) -> List[ArtifactResult]:
        """Write requested artifacts into an existing output folder.

        requested_artifacts must be supported by this generator. Return artifact
        results and let task cancellation reach the caller.
        """
        pass

# Import factory class at the end to avoid circular imports
from .archive_generator_factory import ArchiveGeneratorFactory  # noqa: E402

__all__ = [
    'ArchiveGeneratorStrategyInterface',
    'ArchiveGeneratorFactory',
    'ArtifactResult',
    'ArtifactStatus'
]