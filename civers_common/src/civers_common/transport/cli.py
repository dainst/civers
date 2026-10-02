"""Base class for one-shot CLI transports."""
from abc import abstractmethod
from typing import Any
from civers_common.messaging import CommandBus
from .base import Transport

class CliTransport(Transport):
    def __init__(self, bus: CommandBus):
        super().__init__(bus)

    async def run(self) -> int:
        return await self.execute()

    async def stop(self) -> None:
        return None

    def info(self) -> dict[str, Any]:
        return {"type": "cli"}

    @abstractmethod
    async def execute(self) -> int:
        """Translate CLI input to commands and return an exit code."""
