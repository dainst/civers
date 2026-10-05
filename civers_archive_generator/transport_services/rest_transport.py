"""REST adapter for the CiVers Archive Generator."""

from typing import Any
from uuid import uuid4

from fastapi.responses import JSONResponse
from pydantic import BaseModel

from civers_common import CommandBus, ResultStatus
from civers_common.transport.rest import RestTransport

from domain.commands import ArchiveCommand

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8100


class ArchiveHttpRequest(BaseModel):
    """HTTP request body accepted by POST /archive."""

    url: str
    request_id: str | None = None


class ArchiveRestTransport(RestTransport):
    """Translate HTTP requests to ArchiveCommand objects."""

    def __init__(self, config: Any, bus: CommandBus):
        self.config = config

        rest_config = config.transport.get_transport_config("restapi") or {}

        super().__init__(
            bus=bus,
            host=rest_config.get("host", DEFAULT_HOST),
            port=int(rest_config.get("port", DEFAULT_PORT)),
            title="CiVers Archive Generator REST API",
        )

    def register_routes(self) -> None:
        self.add_route(
            "/archive",
            self._handle_archive,
            methods=["POST"],
        )

    async def _handle_archive(self, request: ArchiveHttpRequest) -> JSONResponse:
        request_id = request.request_id or f"rest-{uuid4().hex}"

        result = await self.bus.dispatch(
            ArchiveCommand(
                request_id=request_id,
                url=request.url,
            )
        )

        if result.success_status is not ResultStatus.FAILED:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "request_id": request_id,
                    **(result.data or {}),
                },
            )

        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "request_id": request_id,
                "error": result.error,
                "error_type": result.error_type,
            },
        )
