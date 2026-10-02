"""Run a transport until completion or a requested shutdown."""

import asyncio
import logging
import os
import signal

from civers_common.configs.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def shutdown_grace_seconds() -> float:
    try:
        value = float(os.getenv("SHUTDOWN_GRACE_SEC", "30"))
    except ValueError as exc:
        raise ConfigurationError("SHUTDOWN_GRACE_SEC must be a finite positive number") from exc
    if not 0 < value < float("inf"):
        raise ConfigurationError("SHUTDOWN_GRACE_SEC must be a finite positive number")
    return value


def install_signal_handlers(event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, event.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(event.set))


async def run_transport(transport, shutdown_event: asyncio.Event, grace_seconds: float) -> int:
    task = asyncio.create_task(transport.run(), name="component-transport")
    shutdown = asyncio.create_task(shutdown_event.wait(), name="component-shutdown")
    stopped = False
    try:
        done, _ = await asyncio.wait([task, shutdown], return_when=asyncio.FIRST_COMPLETED)
        if shutdown in done:
            deadline = asyncio.timeout(grace_seconds)
            try:
                async with deadline:
                    stopped = True
                    await transport.stop()
                    return await asyncio.shield(task)
            except TimeoutError:
                if not deadline.expired():
                    raise
                logger.warning("Shutdown grace period (%ss) expired; cancelling work", grace_seconds)
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                return 0
        return await task
    except Exception:
        logger.exception("Component transport failed")
        return 1
    finally:
        shutdown.cancel()
        if not task.done():
            task.cancel()
        await asyncio.gather(shutdown, task, return_exceptions=True)
        if not stopped:
            await transport.stop()
