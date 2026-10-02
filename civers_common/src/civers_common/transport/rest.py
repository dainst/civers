"""Shared FastAPI/uvicorn transport lifecycle."""
import logging
from collections.abc import Callable
from typing import Any
import uvicorn
from fastapi import FastAPI
from civers_common.messaging import CommandBus
from .base import Transport

logger = logging.getLogger(__name__)

class RestTransport(Transport):
    def __init__(
        self,
        bus: CommandBus,
        *,
        host: str = "0.0.0.0",
        port: int = 8100,
        title: str = "CiVers Metadata Extraction API",
    ):
        super().__init__(bus)
        self.host = host
        self.port = port
        self.app = FastAPI(title=title)
        self._server: uvicorn.Server | None = None
        self._routes_registered = False
        self.app.add_api_route("/health", self._health, methods=["GET"])

    def add_route(self, path: str, handler: Callable, *, methods: list[str] | None = None) -> None:
        self.app.add_api_route(path, handler, methods=methods or ["POST"])

    def register_routes(self) -> None:
        """Override in a component transport."""
        return None

    def _ensure_routes_registered(self) -> None:
        if not self._routes_registered:
            self.register_routes()
            self._routes_registered = True

    async def _health(self) -> dict[str, Any]:
        return {"status": "healthy", "transport": "restapi"}

    async def run(self) -> int:
        self._ensure_routes_registered()
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info")
        self._server = uvicorn.Server(config)
        logger.info("REST API listening on http://%s:%s", self.host, self.port)
        await self._server.serve()
        return 0

    async def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True

    def info(self) -> dict[str, Any]:
        return {"type": "restapi", "host": self.host, "port": self.port}
