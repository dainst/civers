import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from transport_services.cli_transport import ArchiveCliTransport

from civers_common import ResultStatus


def result(*, status, data=None, error=None, error_type=None):
    return SimpleNamespace(
        success_status=status,
        data=data or {},
        error=error,
        error_type=error_type,
    )


@pytest.mark.asyncio
async def test_execute_dispatches_archive_command_and_prints_success(capsys):
    bus = SimpleNamespace(
        dispatch=AsyncMock(
            return_value=result(
                status=SimpleNamespace(value="complete"),
                data={"archive_path": "/archive/r1"},
            )
        )
    )

    transport = ArchiveCliTransport(
        config=object(),
        bus=bus,
        args=[
            "--url",
            "https://example.org",
            "--request-id",
            "r1",
        ],
    )

    exit_code = await transport.execute()

    assert exit_code == 0

    command = bus.dispatch.await_args.args[0]
    assert command.request_id == "r1"
    assert command.url == "https://example.org"

    output = json.loads(capsys.readouterr().out)
    assert output["success"] is True
    assert output["request_id"] == "r1"
    assert output["archive_path"] == "/archive/r1"


@pytest.mark.asyncio
async def test_execute_returns_one_for_domain_failure(capsys):
    bus = SimpleNamespace(
        dispatch=AsyncMock(
            return_value=result(
                status=ResultStatus.FAILED,
                error="archive failed",
                error_type="configuration_not_found",
            )
        )
    )

    transport = ArchiveCliTransport(
        config=object(),
        bus=bus,
        args=[
            "--url",
            "https://example.org",
            "--request-id",
            "r1",
        ],
    )

    assert await transport.execute() == 1

    output = json.loads(capsys.readouterr().err)
    assert output == {
        "success": False,
        "request_id": "r1",
        "error": "archive failed",
        "error_type": "configuration_not_found",
    }


@pytest.mark.asyncio
async def test_execute_returns_argparse_status_for_missing_arguments():
    bus = SimpleNamespace(dispatch=AsyncMock())

    transport = ArchiveCliTransport(
        config=object(),
        bus=bus,
        args=[],
    )

    assert await transport.execute() == 2
    bus.dispatch.assert_not_awaited()
