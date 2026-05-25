"""Tests for typed LoopState, reducers, and HookBus.describe()."""
from __future__ import annotations

from typing import Any

from vulpcode.harness.state import (
    LoopState,
    StateMetadata,
    STATE_SCHEMA_VERSION,
    append_messages,
    evict_messages,
    merge_metadata,
    replace,
)
from vulpcode.harness.hooks import HookBus
from vulpcode.providers.base import Message, Usage


# ---------------------------------------------------------------------------
# Reducer unit tests
# ---------------------------------------------------------------------------


def test_replace_reducer() -> None:
    assert replace(1, 2) == 2
    assert replace("a", "b") == "b"


def test_append_messages() -> None:
    a = Message(role="user", content="a")
    b = Message(role="user", content="b")
    c = Message(role="user", content="c")
    result = append_messages([a], [b, c])
    assert result == [a, b, c]


def test_evict_messages() -> None:
    msgs = [
        Message(role="user", content="a"),
        Message(role="user", content="b"),
        Message(role="user", content="c"),
        Message(role="user", content="d"),
    ]
    result = evict_messages(msgs, [1, 3])
    assert len(result) == 2
    assert result[0].content == "a"
    assert result[1].content == "c"


def test_merge_metadata() -> None:
    old: dict = {"x": 1, "y": 2}
    new: dict = {"y": 99, "z": 3}
    result = merge_metadata(old, new)
    assert result == {"x": 1, "y": 99, "z": 3}


# ---------------------------------------------------------------------------
# LoopState.apply tests
# ---------------------------------------------------------------------------


def test_apply_uses_correct_reducer_for_messages() -> None:
    state = LoopState(messages=[Message(role="user", content="first")])
    new_msg = Message(role="user", content="second")
    updated = state.apply(messages=[new_msg])
    # append_messages should CONCATENATE, not replace
    assert len(updated.messages) == 2
    assert updated.messages[0].content == "first"
    assert updated.messages[1].content == "second"


def test_apply_returns_new_state_not_mutates() -> None:
    state = LoopState(iteration=0)
    updated = state.apply(iteration=5)
    assert updated is not state
    assert updated.iteration == 5
    assert state.iteration == 0


def test_apply_unchanged_fields_preserved() -> None:
    state = LoopState(
        messages=[Message(role="user", content="hi")],
        iteration=3,
        usage=Usage(input_tokens=10),
    )
    updated = state.apply(iteration=4)
    # messages and usage should be preserved
    assert len(updated.messages) == 1
    assert updated.usage.input_tokens == 10
    assert updated.iteration == 4


def test_apply_metadata_uses_merge_reducer() -> None:
    state = LoopState(metadata=StateMetadata(skills_injected=True))
    updated = state.apply(metadata={"last_summarization_iteration": 7})
    # merge_metadata should keep existing keys
    assert updated.metadata.get("skills_injected") is True
    assert updated.metadata.get("last_summarization_iteration") == 7


# ---------------------------------------------------------------------------
# StateMetadata typed access
# ---------------------------------------------------------------------------


def test_state_metadata_typed() -> None:
    state = LoopState()
    meta: StateMetadata = StateMetadata(skills_injected=True)
    updated = state.apply(metadata=meta)
    assert updated.metadata.get("skills_injected") is True  # total=False TypedDict


# ---------------------------------------------------------------------------
# Hook introspection
# ---------------------------------------------------------------------------


def test_hook_with_reads_writes_introspection() -> None:
    bus = HookBus()

    def my_hook(_state: LoopState, **_kw: Any) -> None:
        pass

    my_hook.name = "my_hook"  # type: ignore[attr-defined]
    my_hook.reads = ("messages",)  # type: ignore[attr-defined]
    my_hook.writes = ("metadata",)  # type: ignore[attr-defined]

    bus.register("before_iteration", my_hook)
    desc = bus.describe()  # type: ignore[attr-defined]
    hooks = desc.get("before_iteration", [])
    assert len(hooks) == 1
    assert hooks[0]["name"] == "my_hook"
    assert hooks[0]["reads"] == ("messages",)
    assert hooks[0]["writes"] == ("metadata",)


def test_hook_without_reads_writes_defaults_to_empty() -> None:
    bus = HookBus()

    def plain_hook(_state: LoopState, **_kw: Any) -> None:
        pass

    plain_hook.name = "plain_hook"  # type: ignore[attr-defined]
    bus.register("before_iteration", plain_hook)
    desc = bus.describe()  # type: ignore[attr-defined]
    hooks = desc.get("before_iteration", [])
    assert len(hooks) == 1
    assert hooks[0]["reads"] == ()
    assert hooks[0]["writes"] == ()


# ---------------------------------------------------------------------------
# middleware list helper
# ---------------------------------------------------------------------------


def test_middleware_list_subcommand() -> None:
    from vulpcode.harness import list_middleware  # type: ignore[attr-defined]

    bus = HookBus()

    def hook_a(_state: LoopState, **_kw: Any) -> None:
        pass

    def hook_b(_state: LoopState, **_kw: Any) -> None:
        pass

    hook_a.name = "hook_a"  # type: ignore[attr-defined]
    hook_a.reads = ("messages",)  # type: ignore[attr-defined]
    hook_a.writes = ("metadata",)  # type: ignore[attr-defined]

    hook_b.name = "hook_b"  # type: ignore[attr-defined]
    hook_b.reads = ()  # type: ignore[attr-defined]
    hook_b.writes = ("messages",)  # type: ignore[attr-defined]

    bus.register("before_iteration", hook_a)
    bus.register("after_tool_call", hook_b)

    output = list_middleware(bus)
    assert "hook_a" in output
    assert "hook_b" in output
    assert "before_iteration" in output
    assert "after_tool_call" in output


# ---------------------------------------------------------------------------
# schema version
# ---------------------------------------------------------------------------


def test_state_schema_version_is_one() -> None:
    assert STATE_SCHEMA_VERSION == 1
    state = LoopState()
    assert state.version == 1
