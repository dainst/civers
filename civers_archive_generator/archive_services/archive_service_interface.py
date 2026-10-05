"""Interface for services that handle archive commands."""

from abc import ABC, abstractmethod
from civers_common import Result

from domain.commands import ArchiveCommand


class ArchiveServiceInterface(ABC):
    """Required methods for an archive command handler."""

    @abstractmethod
    async def execute(self, command: ArchiveCommand) -> Result:
        """Handle an archive command and return its Result.

        Use COMPLETE or PARTIAL when artifacts were created, and FAILED otherwise.
        Let task cancellation reach the caller.
        """
        pass
