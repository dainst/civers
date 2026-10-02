from unittest.mock import AsyncMock

import pytest

from civers_common.transport.cli import CliTransport


class DummyCliTransport(CliTransport):
    async def execute(self) -> int:
        return 7


@pytest.mark.asyncio
async def test_run_delegates_to_execute():
    transport = DummyCliTransport(bus=object())

    assert await transport.run() == 7


@pytest.mark.asyncio
async def test_stop_is_safe_noop():
    transport = DummyCliTransport(bus=object())

    assert await transport.stop() is None
    assert await transport.stop() is None


def test_info():
    transport = DummyCliTransport(bus=object())

    assert transport.info() == {"type": "cli"}
