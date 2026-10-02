"""In-process command/message bus (mediator).

The bus is the sole bridge between transport adapters and domain handlers. Adapters
``dispatch`` a :class:`Command`; the bus routes it to the handler registered for that
command type and returns a :class:`Result`. Handlers may be sync or async — the bus
awaits awaitable results so a synchronous transport and an asynchronous one can share
the same domain.
"""

import inspect
from collections.abc import Awaitable, Callable

from .contracts import Command, Result

Handler = Callable[[Command], Result | Awaitable[Result]]


class CommandBus:
    """Routes commands to their registered handler."""

    def __init__(self) -> None:
        self._handlers: dict[type[Command], Handler] = {}

    def register(self, command_type: type[Command], handler: Handler) -> None:
        """Register the handler for a command type (one handler per type)."""
        if command_type in self._handlers:
            raise ValueError(f"Handler already registered for {command_type.__name__}")
        self._handlers[command_type] = handler

    async def dispatch(self, command: Command) -> Result:
        """Route a command to its handler and return the Result."""
        try:
            handler = self._handlers[type(command)]
        except KeyError as exc:
            raise LookupError(
                f"No handler registered for {type(command).__name__}"
            ) from exc
        outcome = handler(command)
        if inspect.isawaitable(outcome):
            outcome = await outcome
        return outcome
