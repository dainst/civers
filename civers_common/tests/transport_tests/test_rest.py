from unittest.mock import AsyncMock, MagicMock

import pytest

from civers_common.transport.rest import RestTransport


class DummyRestTransport(RestTransport):
    def __init__(self):
        super().__init__(
            bus=object(),
            host="127.0.0.1",
            port=9999,
            title="Test API",
        )
        self.register_count = 0

    def register_routes(self) -> None:
        self.register_count += 1

        async def handler():
            return {"ok": True}

        self.add_route("/work", handler)


def test_routes_are_registered_once():
    transport = DummyRestTransport()

    transport._ensure_routes_registered()
    transport._ensure_routes_registered()

    assert transport.register_count == 1

    paths = {route.path for route in transport.app.routes}
    assert "/work" in paths
    assert "/health" in paths


@pytest.mark.asyncio
async def test_health():
    transport = DummyRestTransport()

    assert await transport._health() == {
        "status": "healthy",
        "transport": "restapi",
    }


@pytest.mark.asyncio
async def test_run_starts_uvicorn(monkeypatch):
    transport = DummyRestTransport()

    server = MagicMock()
    server.serve = AsyncMock(return_value=None)

    server_class = MagicMock(return_value=server)
    config_class = MagicMock(return_value=object())

    monkeypatch.setattr("civers_common.transport.rest.uvicorn.Config", config_class)
    monkeypatch.setattr("civers_common.transport.rest.uvicorn.Server", server_class)

    result = await transport.run()

    assert result == 0
    assert transport.register_count == 1

    config_class.assert_called_once()
    server_class.assert_called_once()
    server.serve.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_requests_server_shutdown():
    transport = DummyRestTransport()

    server = MagicMock()
    server.should_exit = False
    transport._server = server

    await transport.stop()

    assert server.should_exit is True


def test_info():
    transport = DummyRestTransport()

    assert transport.info() == {
        "type": "restapi",
        "host": "127.0.0.1",
        "port": 9999,
    }
