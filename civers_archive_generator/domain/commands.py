"""Archive capture commands."""

from civers_common import Command


class ArchiveCommand(Command):
    """Request to archive a single URL. Built by adapters, handled by ArchiveService."""

    url: str
