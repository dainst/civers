"""Exercise actual process exit codes and signal handlers without external services."""

from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize("outcome,exit_code", [("startup_error", 1), ("transport_error", 1), ("sigterm", 0)])
def test_process_failure_and_requested_shutdown(outcome, exit_code):
    script = textwrap.dedent(f"""
        import asyncio
        import os
        import signal
        import sys
        from unittest.mock import AsyncMock
        import main

        class Transport:
            async def run(self):
                if {outcome!r} == "transport_error":
                    raise RuntimeError("broker down")
                try:
                    os.kill(os.getpid(), signal.SIGTERM)
                    await asyncio.Event().wait()
                finally:
                    print("capture cancellation cleanup completed", flush=True)

            async def stop(self):
                pass

        app = main.ArchiveGeneratorApp()
        app.shutdown_grace_sec = 0.02
        app.transport = Transport()
        app.initialize = AsyncMock(
            side_effect=RuntimeError("configuration failed") if {outcome!r} == "startup_error" else None
        )
        sys.exit(asyncio.run(app.run()))
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        text=True, capture_output=True, timeout=10,
    )
    assert result.returncode == exit_code, result.stdout + result.stderr
    if outcome == "sigterm":
        assert "capture cancellation cleanup completed" in result.stdout
