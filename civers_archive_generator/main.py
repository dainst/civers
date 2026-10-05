"""Connect configuration, the archive command handler and the selected transport."""
import asyncio
import contextlib
from importlib import import_module
import os
from pathlib import Path
import sys

from civers_common import CommandBus, ConfigurationError
from civers_common.transport import Transport
from civers_common.transport.lifecycle import install_signal_handlers, run_transport, shutdown_grace_seconds

from archive_services import ArchiveService
from configs.loaders import YamlFileConfigLoader
from configs.logging_config import get_logger, resolve_log_level, setup_logging
from domain.commands import ArchiveCommand


setup_logging(
    level=resolve_log_level(os.getenv("LOG_LEVEL")),
    log_file=os.getenv("LOG_FILE") or None,
    suppress_kafka_logs=True,
)

logger = get_logger(__name__)

TRANSPORTS = {
    "kafka": ("transport_services.kafka_transport", "ArchiveKafkaTransport"),
    "restapi": ("transport_services.rest_transport", "ArchiveRestTransport"),
    "cli": ("transport_services.cli_transport", "ArchiveCliTransport"),
}

def load_config():
    loader = YamlFileConfigLoader(
        config_dir=Path(os.environ["CONFIG_DIR"]) if os.getenv("CONFIG_DIR") else None,
        environment=os.getenv("CONFIG_ENVIRONMENT"),
    )
    return loader.load()

def create_transport(config, bus: CommandBus) -> Transport:
    enabled = list(config.transport.enabled)

    if not enabled:
        raise ConfigurationError("No transport is enabled")

    if len(enabled) != 1:
        raise ConfigurationError(
            f"Archive Generator runs one transport per process; configured: {enabled}"
        )

    name = enabled[0]
    try:
        module, class_name = TRANSPORTS[name]
    except KeyError as exc:
        raise ConfigurationError(
            f"Unknown transport {name!r}; available: {sorted(TRANSPORTS)}"
        ) from exc

    transport_class = getattr(import_module(module), class_name)
    return transport_class(config=config, bus=bus)

class ArchiveGeneratorApp:
    def __init__(self):
        self.transport: Transport | None = None
        self.exit_code = 0
        self._stopping = False
        self._shutdown_event = asyncio.Event()
        self.shutdown_grace_sec = shutdown_grace_seconds()

    async def initialize(self) -> None:
        config = load_config()

        archive_service = ArchiveService(config)

        bus = CommandBus()
        bus.register(ArchiveCommand, archive_service.execute)

        self.transport = create_transport(config, bus)

        logger.info("Selected transport: %s", self.transport.info())

    async def run(self) -> int:
        await self.initialize()

        if self.transport is None:
            raise RuntimeError("Transport was not initialized")

        self._install_signal_handlers()
        self.exit_code = await run_transport(
            self.transport, self._shutdown_event, self.shutdown_grace_sec
        )
        return self.exit_code

    async def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True

        if self.transport is not None:
            with contextlib.suppress(Exception):
                await self.transport.stop()

    def _install_signal_handlers(self) -> None:
        install_signal_handlers(self._shutdown_event)

async def main() -> int:
    return await ArchiveGeneratorApp().run()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
