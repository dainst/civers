import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from transport_services.rest_transport import (
    ArchiveHttpRequest,
    ArchiveRestTransport,
)

from civers_common import ResultStatus


class TransportConfig:
    def __init__(self, rest=None):
        self.rest = rest

    def get_transport_config(self, name):
        assert name == "restapi"
        return self.rest


def config(rest=None):
    return SimpleNamespace(transport=TransportConfig(rest))


def result(*, status, data=None, error=None, error_type=None):
    return SimpleNamespace(
        success_status=status,
        data=data or {},
        error=error,
        error_type=error_type,
    )


def response_json(response):
    return json.loads(response.body.decode("utf-8"))


def test_constructor_reads_rest_config():
    transport = ArchiveRestTransport(
        config(
            {
                "host": "127.0.0.1",
                "port": "9001",
            }
        ),
        bus=object(),
    )

    assert transport.host == "127.0.0.1"
    assert transport.port == 9001


def test_constructor_uses_defaults_when_rest_config_absent():
    transport = ArchiveRestTransport(
        config(None),
        bus=object(),
    )

    assert transport.host == "0.0.0.0"
    assert transport.port == 8100


@pytest.mark.asyncio
async def test_archive_request_dispatches_command_and_returns_success():
    bus = SimpleNamespace(
        dispatch=AsyncMock(
            return_value=result(
                status=SimpleNamespace(value="complete"),
                data={"archive_path": "/archive/r1"},
            )
        )
    )

    transport = ArchiveRestTransport(config({}), bus)

    response = await transport._handle_archive(
        ArchiveHttpRequest(
            request_id="r1",
            url="https://example.org",
        )
    )

    assert response.status_code == 200

    body = response_json(response)
    assert body == {
        "success": True,
        "request_id": "r1",
        "archive_path": "/archive/r1",
    }

    command = bus.dispatch.await_args.args[0]
    assert command.request_id == "r1"
    assert command.url == "https://example.org"


@pytest.mark.asyncio
async def test_archive_request_generates_request_id_when_missing():
    bus = SimpleNamespace(
        dispatch=AsyncMock(
            return_value=result(
                status=SimpleNamespace(value="complete"),
            )
        )
    )

    transport = ArchiveRestTransport(config({}), bus)

    response = await transport._handle_archive(
        ArchiveHttpRequest(url="https://example.org")
    )

    body = response_json(response)
    assert body["request_id"].startswith("rest-")

    command = bus.dispatch.await_args.args[0]
    assert command.request_id == body["request_id"]


@pytest.mark.asyncio
async def test_domain_failure_returns_400():
    bus = SimpleNamespace(
        dispatch=AsyncMock(
            return_value=result(
                status=ResultStatus.FAILED,
                error="not allowed",
                error_type="validation_error",
            )
        )
    )

    transport = ArchiveRestTransport(config({}), bus)

    response = await transport._handle_archive(
        ArchiveHttpRequest(
            request_id="r1",
            url="https://example.org",
        )
    )

    assert response.status_code == 400
    assert response_json(response) == {
        "success": False,
        "request_id": "r1",
        "error": "not allowed",
        "error_type": "validation_error",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("failed,expected_status", [(False, 200), (True, 400)])
async def test_registered_http_route_dispatches_real_command(failed, expected_status):
    from domain.commands import ArchiveCommand

    from civers_common import CommandBus, Result

    dispatched = []

    async def handle(command):
        dispatched.append(command)
        return (
            Result.fail("capture failed", "capture_error")
            if failed
            else Result.ok(archive_path="/tmp/archive")
        )

    bus = CommandBus()
    bus.register(ArchiveCommand, handle)
    transport = ArchiveRestTransport(config({}), bus)
    transport._ensure_routes_registered()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=transport.app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/archive", json={"url": "https://example.com", "request_id": "req-1"}
        )

    assert response.status_code == expected_status
    assert response.json()["success"] is not failed
    assert response.json()["request_id"] == "req-1"
    assert len(dispatched) == 1
    assert dispatched[0].url == "https://example.com"


@pytest.mark.asyncio
async def test_http_missing_url_is_rejected_before_dispatch():
    bus = SimpleNamespace(dispatch=AsyncMock())
    transport = ArchiveRestTransport(config({}), bus)
    transport._ensure_routes_registered()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=transport.app), base_url="http://test"
    ) as client:
        response = await client.post("/archive", json={"request_id": "req-1"})
    assert response.status_code == 422
    bus.dispatch.assert_not_awaited()
