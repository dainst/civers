import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import main as main_module


def app_config(enabled):
    return SimpleNamespace(
        transport=SimpleNamespace(enabled=enabled),
        app=SimpleNamespace(
            name="Archive Generator",
            version="test",
        ),
    )


class FakeTransport:
    def __init__(self, config, bus):
        self.config = config
        self.bus = bus

    async def run(self) -> int:
        return 0

    async def stop(self) -> None:
        return None

    def info(self):
        return {"type": "fake"}


def test_create_transport_selects_enabled_transport(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "TRANSPORTS",
        {"kafka": (__name__, "FakeTransport")},
    )

    config = app_config(["kafka"])
    bus = object()

    transport = main_module.create_transport(config, bus)

    assert isinstance(transport, FakeTransport)
    assert transport.config is config
    assert transport.bus is bus


def test_create_transport_requires_one_enabled_transport():
    with pytest.raises(main_module.ConfigurationError, match="No transport"):
        main_module.create_transport(app_config([]), object())

    with pytest.raises(
        main_module.ConfigurationError,
        match="one transport per process",
    ):
        main_module.create_transport(
            app_config(["kafka", "restapi"]),
            object(),
        )


def test_create_transport_rejects_unknown_transport():
    with pytest.raises(main_module.ConfigurationError, match="Unknown transport"):
        main_module.create_transport(
            app_config(["rabbitmq"]),
            object(),
        )


@pytest.mark.asyncio
async def test_initialize_wires_service_to_command_bus(monkeypatch):
    config = app_config(["kafka"])
    monkeypatch.setattr(main_module, "load_config", lambda: config)

    service = MagicMock()
    service.execute = AsyncMock()
    archive_service_class = MagicMock(return_value=service)
    monkeypatch.setattr(
        main_module,
        "ArchiveService",
        archive_service_class,
    )

    bus = MagicMock()
    bus_class = MagicMock(return_value=bus)
    monkeypatch.setattr(main_module, "CommandBus", bus_class)

    transport = MagicMock()
    transport.info.return_value = {"type": "kafka"}

    create_transport = MagicMock(return_value=transport)
    monkeypatch.setattr(
        main_module,
        "create_transport",
        create_transport,
    )

    app = main_module.ArchiveGeneratorApp()
    await app.initialize()

    archive_service_class.assert_called_once_with(config)
    bus.register.assert_called_once_with(main_module.ArchiveCommand, service.execute)
    create_transport.assert_called_once_with(config, bus)
    assert app.transport is transport


@pytest.mark.asyncio
async def test_run_returns_transport_exit_code_and_stops(monkeypatch):
    transport = MagicMock()
    transport.run = AsyncMock(return_value=7)
    transport.stop = AsyncMock()

    app = main_module.ArchiveGeneratorApp()
    app.transport = transport

    app.initialize = AsyncMock()
    app._install_signal_handlers = MagicMock()

    result = await app.run()

    assert result == 7
    assert app.exit_code == 7
    transport.run.assert_awaited_once()
    transport.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_converts_transport_exception_to_exit_code_one():
    transport = MagicMock()
    transport.run = AsyncMock(side_effect=RuntimeError("boom"))
    transport.stop = AsyncMock()

    app = main_module.ArchiveGeneratorApp()
    app.transport = transport

    app.initialize = AsyncMock()
    app._install_signal_handlers = MagicMock()

    result = await app.run()

    assert result == 1
    assert app.exit_code == 1
    transport.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    transport = MagicMock()
    transport.stop = AsyncMock()

    app = main_module.ArchiveGeneratorApp()
    app.transport = transport

    await app.stop()
    await app.stop()

    transport.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_allows_inflight_work_to_finish():
    started, intake_stopped, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def run():
        started.set()
        await intake_stopped.wait()
        await asyncio.sleep(0)
        completed.set()
        return 0

    transport = SimpleNamespace(run=run, stop=AsyncMock(side_effect=intake_stopped.set))
    app = main_module.ArchiveGeneratorApp()
    app.transport = transport
    app.initialize = AsyncMock()
    app._install_signal_handlers = MagicMock()
    app.shutdown_grace_sec = 1
    task = asyncio.create_task(app.run())
    await started.wait()
    app._shutdown_event.set()

    assert await asyncio.wait_for(task, 2) == 0
    assert completed.is_set()
    transport.stop.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("stuck_intake", [False, True])
async def test_shutdown_cancels_unfinished_work_and_awaits_cleanup(stuck_intake):
    started, cleaned = asyncio.Event(), asyncio.Event()

    async def run():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleaned.set()

    async def stop():
        if stuck_intake:
            await asyncio.Event().wait()

    transport = SimpleNamespace(run=run, stop=AsyncMock(side_effect=stop))
    app = main_module.ArchiveGeneratorApp()
    app.transport = transport
    app.initialize = AsyncMock()
    app._install_signal_handlers = MagicMock()
    app.shutdown_grace_sec = 0.02
    task = asyncio.create_task(app.run())
    await started.wait()
    app._shutdown_event.set()
    app._shutdown_event.set()  # Repeated signals do not start competing shutdowns.

    assert await asyncio.wait_for(task, 1) == 0
    assert cleaned.is_set()
    transport.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_cancels_pending_browsertrix_job(tmp_path):
    from archive_generators.browsertrix.browsertrix_generator import BrowsertrixGenerator

    jobs, output = tmp_path / "jobs", tmp_path / "output"
    jobs.mkdir()
    output.mkdir()
    generator = BrowsertrixGenerator(SimpleNamespace(app=SimpleNamespace(
        browsertrix_jobs_dir=str(jobs), browsertrix_timeout_sec=30,
        browsertrix_extra_args=[],
    )))

    async def run():
        await generator.generate_archive("https://example.com/", output, ["warc"])
        return 0

    app = main_module.ArchiveGeneratorApp()
    app.transport = SimpleNamespace(run=run, stop=AsyncMock())
    app.initialize = AsyncMock()
    app._install_signal_handlers = MagicMock()
    app.shutdown_grace_sec = 0.02
    task = asyncio.create_task(app.run())
    async with asyncio.timeout(1):
        while not list(jobs.glob("*/cmd.json")):
            await asyncio.sleep(0)
    app._shutdown_event.set()

    assert await asyncio.wait_for(task, 1) == 0
    job = next(jobs.iterdir())
    assert (job / "cancel").exists()
    assert not (job / "ack").exists()


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "invalid"])
def test_shutdown_grace_must_be_positive_and_finite(monkeypatch, value):
    monkeypatch.setenv("SHUTDOWN_GRACE_SEC", value)
    with pytest.raises(main_module.ConfigurationError):
        main_module.ArchiveGeneratorApp()


@pytest.mark.asyncio
async def test_transport_timeout_during_drain_still_exits_with_failure():
    app = main_module.ArchiveGeneratorApp()

    async def run():
        await app._shutdown_event.wait()
        raise TimeoutError("broker timeout")

    app.transport = SimpleNamespace(run=run, stop=AsyncMock())
    app.initialize = AsyncMock()
    app._install_signal_handlers = MagicMock()
    app._shutdown_event.set()
    assert await app.run() == 1
