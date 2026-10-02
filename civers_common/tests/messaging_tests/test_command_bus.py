"""Tests for the CommandBus / command dispatcher."""

import asyncio

import pytest

from civers_common.messaging import ResultStatus, Command, CommandBus, Result


class _AsyncCommand(Command):
    value: str


class _SyncCommand(Command):
    value: str


class _UnregisteredCommand(Command):
    pass


class TestCommandBus:
    def test_dispatch_async_handler(self):
        bus = CommandBus()

        async def handle(cmd: _AsyncCommand) -> Result:
            return Result.ok(echo=cmd.value)

        bus.register(_AsyncCommand, handle)
        result = asyncio.run(bus.dispatch(_AsyncCommand(request_id="r", value="hi")))
        assert result.success_status is ResultStatus.COMPLETE
        assert result.data["echo"] == "hi"

    def test_dispatch_sync_handler(self):
        bus = CommandBus()

        def handle(cmd: _SyncCommand) -> Result:
            return Result.ok(echo=cmd.value)

        bus.register(_SyncCommand, handle)
        result = asyncio.run(bus.dispatch(_SyncCommand(request_id="r", value="yo")))
        assert result.data["echo"] == "yo"

    def test_duplicate_registration_rejected(self):
        bus = CommandBus()
        bus.register(_AsyncCommand, lambda c: Result.ok())
        with pytest.raises(ValueError, match="already registered"):
            bus.register(_AsyncCommand, lambda c: Result.ok())

    def test_dispatch_unregistered_raises(self):
        bus = CommandBus()
        with pytest.raises(LookupError, match="No handler"):
            asyncio.run(bus.dispatch(_UnregisteredCommand(request_id="r")))
