"""Archive commands remain immutable while crossing the command bus."""

import pytest
from domain.commands import ArchiveCommand
from pydantic import ValidationError


@pytest.mark.unit
def test_archive_command_is_frozen():
    command = ArchiveCommand(request_id="req-1", url="https://example.com")

    with pytest.raises(ValidationError, match="frozen_instance"):
        command.url = "https://changed.com"
