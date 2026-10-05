"""An archive service implementation only needs the command execution contract."""

import pytest

from civers_common import CommandBus, Result, ResultStatus
from archive_services import ArchiveServiceInterface
from domain.commands import ArchiveCommand


class ExecuteOnlyService(ArchiveServiceInterface):
    async def execute(self, command: ArchiveCommand) -> Result:
        return Result.ok(request_id=command.request_id, url=command.url)


@pytest.mark.unit
async def test_execute_only_implementation_handles_archive_command():
    service = ExecuteOnlyService()
    bus = CommandBus()
    bus.register(ArchiveCommand, service.execute)
    command = ArchiveCommand(request_id="req-1", url="https://example.com/page")

    result = await bus.dispatch(command)

    assert result.success_status is ResultStatus.COMPLETE
    assert result.data == {"request_id": command.request_id, "url": command.url}
