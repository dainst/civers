"""Command / Result contracts — the internal application boundary.

Commands are the transport-agnostic *requests* that adapters build from raw payloads and
hand to the ``CommandBus``. Results are the transport-agnostic *outcomes* that domain
handlers return and adapters translate into a transport-specific response (Kafka event,
HTTP status, stdout, …). Neither knows anything about a transport.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class Command(BaseModel):
    """Base for all commands; carries the correlation id."""

    model_config = ConfigDict(frozen=True)

    request_id: str


class ResultStatus(str, Enum):
    """How a command turned out.

    A handler can finish without doing the whole job. A boolean cannot say that, and
    the difference is exactly what a consumer needs to decide about retrying or
    alerting — so the outcome is these three states rather than yes and no.
    """

    COMPLETE = "complete"   # everything that was asked for
    PARTIAL = "partial"     # less than that, but what came back is usable
    FAILED = "failed"       # nothing usable


class Result(BaseModel):
    """Standardized outcome of handling a command.

    One field says how it went. There is no separate boolean: two fields describing a
    single outcome can drift apart, and the one that says less would win by being the
    one everybody reads.
    """

    success_status: ResultStatus
    data: dict[str, Any] = {}
    error: str | None = None
    error_type: str | None = None

    @classmethod
    def ok(cls, **data: Any) -> "Result":
        """Build a result for work that did everything it was asked to."""
        return cls(success_status=ResultStatus.COMPLETE, data=data)

    @classmethod
    def partial(cls, **data: Any) -> "Result":
        """Build a result for work that produced something usable, but not all of it.

        ``data`` should say what is absent, so a consumer can act on it.
        """
        return cls(success_status=ResultStatus.PARTIAL, data=data)

    @classmethod
    def fail(cls, error: str, error_type: str | None = None, **data: Any) -> "Result":
        """Build a result for work that produced nothing usable.

        ``data`` carries whatever the work did manage to produce before giving up — the
        failure path is the one a consumer most needs facts from. As with ``ok``, a key
        literally named ``error`` or ``error_type`` cannot be passed this way.
        """
        return cls(
            success_status=ResultStatus.FAILED,
            error=error,
            error_type=error_type,
            data=data,
        )
