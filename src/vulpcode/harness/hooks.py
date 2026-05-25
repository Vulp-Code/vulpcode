"""HookBus: registry + dispatcher for agent-loop middleware events."""
from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from vulpcode.harness.state import LoopState

logger = logging.getLogger(__name__)


@runtime_checkable
class Hook(Protocol):
    name: str
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()

    def __call__(self, state: LoopState, **kwargs: Any) -> object | None: ...


_VALID_EVENTS = frozenset(
    {"before_iteration", "before_send", "before_tool_call", "after_tool_call", "before_compress"}
)


class HookBus:
    """Registry and dispatcher for middleware hooks. Not async."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[Any]] = {e: [] for e in _VALID_EVENTS}

    def register(self, event: str, hook: Any) -> None:
        """Register *hook* for *event*. Hooks fire in registration order."""
        if event not in self._hooks:
            raise ValueError(f"Unknown event {event!r}. Valid: {sorted(_VALID_EVENTS)}")
        self._hooks[event].append(hook)

    def emit(self, event: str, state: LoopState, **kwargs: Any) -> list[object]:
        """Call all hooks for *event* in order. Returns list of return values.

        Exceptions from individual hooks are logged and swallowed so one bad
        hook cannot abort the agent loop.
        """
        if event not in self._hooks:
            raise ValueError(f"Unknown event {event!r}")
        returns: list[object] = []
        for hook in self._hooks[event]:
            try:
                rv = hook(state, **kwargs)
                returns.append(rv)
            except Exception:
                hook_name = getattr(hook, "name", repr(hook))
                logger.exception("Hook %r raised during event %r; continuing", hook_name, event)
        return returns

    def describe(self) -> dict[str, list[dict]]:
        """Return hook metadata per event. Used by `vulp middleware list`."""
        result: dict[str, list[dict]] = {}
        for event, hooks in self._hooks.items():
            if not hooks:
                continue
            entries = []
            for hook in hooks:
                entries.append(
                    {
                        "name": getattr(hook, "name", repr(hook)),
                        "reads": getattr(hook, "reads", ()),
                        "writes": getattr(hook, "writes", ()),
                    }
                )
            result[event] = entries
        return result
