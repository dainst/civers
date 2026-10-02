"""Small transport contract shared by all CiVers transports."""
from abc import ABC, abstractmethod
from typing import Any
from civers_common.messaging import CommandBus

class Transport(ABC):
    def __init__(self, bus: CommandBus):
        self.bus = bus

    @abstractmethod
    async def run(self) -> int:
        """Run the transport and return the process exit code."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport; safe to call more than once."""

    @abstractmethod
    def info(self) -> dict[str, Any]:
        """Return non-secret descriptive information."""
