"""CLI adapter for the CiVers Archive Generator."""

import argparse
import json
import sys
from typing import Any

from civers_common import CommandBus, ResultStatus
from civers_common.transport import CliTransport

from domain.commands import ArchiveCommand


class ArchiveCliTransport(CliTransport):
    """Run one archive request from command-line arguments."""

    def __init__(
        self,
        config: Any,
        bus: CommandBus,
        args: list[str] | None = None,
    ):
        super().__init__(bus)
        self.config = config
        self.args = args if args is not None else sys.argv[1:]

    def _parse(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(
            description="CiVers Archive Generator CLI"
        )
        parser.add_argument(
            "--url",
            required=True,
            help="URL to archive",
        )
        parser.add_argument(
            "--request-id",
            required=True,
            help="Trace request ID",
        )

        # Ignore extra arguments supplied by process wrappers.
        parsed, _ = parser.parse_known_args(self.args)
        return parsed

    async def execute(self) -> int:
        try:
            parsed = self._parse()
        except SystemExit as usage:
            # argparse already wrote help/usage to the correct stream.
            return int(usage.code or 0)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        result = await self.bus.dispatch(
            ArchiveCommand(
                request_id=parsed.request_id,
                url=parsed.url,
            )
        )

        if result.success_status is not ResultStatus.FAILED:
            print(
                json.dumps(
                    {
                        "success": True,
                        "request_id": parsed.request_id,
                        **(result.data or {}),
                    },
                    default=str,
                )
            )
            return 0

        print(
            json.dumps(
                {
                    "success": False,
                    "request_id": parsed.request_id,
                    "error": result.error,
                    "error_type": result.error_type,
                },
                default=str,
            ),
            file=sys.stderr,
        )
        return 1
