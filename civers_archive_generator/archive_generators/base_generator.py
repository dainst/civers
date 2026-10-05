"""Shared base class for archive generators."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, List

import aiofiles

from .archive_result import ArtifactResult
from . import ArchiveGeneratorStrategyInterface

if TYPE_CHECKING:
    from configs.models import ConfigDataModel

class BaseGenerator(ArchiveGeneratorStrategyInterface):
    """Base class for archive generators with shared utilities."""

    def __init__(self, config: ConfigDataModel):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def _save_log_to_file(self, content: bytes, folder: str, filename: str) -> str:
        """Write a capture log and return its target path, even if writing fails."""
        log_path = os.path.join(folder, filename)
        try:
            async with aiofiles.open(log_path, "wb") as f:
                await f.write(content or b"")
            self.logger.debug(f"Saved log to: {log_path}")
        except Exception as e:
            self.logger.error(f"Failed to save log to {log_path}: {e}")
        return log_path

    async def generate_archive(
        self, 
        url: str, 
        output_folder: str, 
        requested_artifacts: List[str]
    ) -> List[ArtifactResult]:
        """Generate specified archive artifacts. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement generate_archive")

    def get_capabilities(self) -> List[str]:
        """Return the list of artifact types this generator can produce."""
        return self.CAPABILITIES

    def get_generator_name(self) -> str:
        """Return the lowercase class name used in capture metadata."""
        return self.__class__.__name__.lower()