"""Typed LoopState with explicit per-field reducers."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Annotated, Any, Callable, TypeVar, TypedDict, get_args, get_origin, get_type_hints

from vulpcode.providers.base import Message, Usage

T = TypeVar("T")
Reducer = Callable[[T, T], T]

STATE_SCHEMA_VERSION: int = 1


def replace(_old: T, new: T) -> T:
    """Default reducer: new replaces old."""
    return new


def append_messages(old: list[Message], new: list[Message]) -> list[Message]:
    """Concatenate message lists. Use to add messages while preserving history."""
    return [*old, *new]


def evict_messages(old: list[Message], indices_to_drop: list[int]) -> list[Message]:
    """Eviction reducer. indices_to_drop is a list of indices to remove."""
    drop = set(indices_to_drop)
    return [m for i, m in enumerate(old) if i not in drop]


def merge_metadata(old: dict, new: dict) -> dict:
    """Dict merge — keys in new override old. Allows incremental updates."""
    return {**old, **new}


class StateMetadata(TypedDict, total=False):
    """Known metadata keys used by middleware. Declare new keys here."""

    skills_injected: bool
    active_skill_tools_allow: list[str] | None
    last_summarization_iteration: int
    last_block_message: str
    handle_ids_emitted_this_turn: list[str]


@dataclass
class LoopState:
    """Canonical state snapshot for one agent-loop iteration.

    Each field has an associated reducer declared via Annotated.
    Use state.apply(**updates) to produce a new state applying reducers.
    Direct mutation (state.messages.append(...)) still works for backward compat.
    """

    messages: Annotated[list[Message], append_messages] = field(default_factory=list)
    usage: Annotated[Usage, replace] = field(default_factory=Usage)
    iteration: Annotated[int, replace] = 0
    metadata: Annotated[StateMetadata, merge_metadata] = field(
        default_factory=lambda: StateMetadata()
    )
    version: int = STATE_SCHEMA_VERSION

    def _reducer_for(self, field_name: str) -> Reducer:
        hints = get_type_hints(type(self), include_extras=True)
        annotation = hints.get(field_name)
        if annotation is not None and get_origin(annotation) is Annotated:
            args = get_args(annotation)
            if len(args) >= 2 and callable(args[1]):
                return args[1]  # type: ignore[return-value]
        return replace  # type: ignore[return-value]

    def apply(self, **updates: Any) -> "LoopState":
        """Apply updates field-by-field using declared reducers.

        Returns a NEW LoopState — does not mutate self.
        """
        new_data: dict[str, Any] = {}
        for f in dataclasses.fields(self):
            if f.name in updates:
                reducer = self._reducer_for(f.name)
                new_data[f.name] = reducer(getattr(self, f.name), updates[f.name])
            else:
                new_data[f.name] = getattr(self, f.name)
        return LoopState(**new_data)
