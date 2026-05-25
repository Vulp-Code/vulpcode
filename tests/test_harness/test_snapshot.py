"""Tests for harness snapshot: dump, load, migrate, slash command."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from vulpcode.harness.snapshot import (
    dump_state,
    latest_snapshot,
    load_state,
)
from vulpcode.harness.state import LoopState, StateMetadata
from vulpcode.providers.base import Message, Usage


# ---------------------------------------------------------------------------
# dump / load
# ---------------------------------------------------------------------------


def test_dump_creates_json_file(tmp_path: Path) -> None:
    state = LoopState(messages=[], iteration=0)
    path = dump_state(state, session_id="s1", iteration=0, base_dir=tmp_path)
    assert path.exists()
    assert path.suffix == ".json"


def test_dump_roundtrip(tmp_path: Path) -> None:
    msgs = [
        Message(role="user", content="hello"),
        Message(role="assistant", content="hi"),
    ]
    meta: StateMetadata = StateMetadata(skills_injected=True)
    state = LoopState(
        messages=msgs,
        usage=Usage(input_tokens=5, output_tokens=3),
        iteration=7,
        metadata=meta,
    )
    path = dump_state(state, session_id="sess", iteration=7, base_dir=tmp_path)
    restored = load_state(path)

    assert restored.iteration == 7
    assert len(restored.messages) == 2
    assert restored.messages[0].content == "hello"
    assert restored.messages[1].content == "hi"
    assert restored.usage.input_tokens == 5
    assert restored.usage.output_tokens == 3
    assert restored.metadata.get("skills_injected") is True


def test_load_unknown_version_raises(tmp_path: Path) -> None:
    payload = {
        "schema_version": 999,
        "session_id": "x",
        "iteration": 0,
        "messages": [],
        "usage": {},
        "metadata": {},
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="migrate"):
        load_state(p)


def test_latest_snapshot_picks_highest_iter(tmp_path: Path) -> None:
    state = LoopState()
    for n in (5, 10, 7):
        dump_state(state, session_id="sess", iteration=n, base_dir=tmp_path)
    latest = latest_snapshot("sess", base_dir=tmp_path)
    assert latest is not None
    assert "iter_10" in latest.name


def test_provider_not_serialized(tmp_path: Path) -> None:
    state = LoopState()
    path = dump_state(state, session_id="sess", iteration=0, base_dir=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "provider" not in data


# ---------------------------------------------------------------------------
# slash command
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_save_command(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr("vulpcode.harness.snapshot.SNAPSHOT_DIR", tmp_path)
    # also patch in snapshot_cmd module if it imported SNAPSHOT_DIR at import time
    import vulpcode.commands.snapshot_cmd as sc_mod
    monkeypatch.setattr(sc_mod, "_get_snapshot_dir", lambda: tmp_path, raising=False)

    from vulpcode.commands.snapshot_cmd import SnapshotCommand

    agent = MagicMock()
    agent._messages = [Message(role="user", content="hi")]
    agent._session_usage = Usage()
    agent.session_id = "test-session"

    printed: list[str] = []

    repl = MagicMock()
    repl.agent = agent
    repl.renderer.console.print = lambda msg: printed.append(msg)

    cmd = SnapshotCommand()
    await cmd.run(repl, "save")

    # file should exist in tmp_path / "test-session"
    session_dir = tmp_path / "test-session"
    snapshots = list(session_dir.glob("iter_*.json"))
    assert len(snapshots) == 1
    assert any("snapshot saved" in p for p in printed)


@pytest.mark.asyncio
async def test_snapshot_list_command(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr("vulpcode.harness.snapshot.SNAPSHOT_DIR", tmp_path)
    import vulpcode.commands.snapshot_cmd as sc_mod
    monkeypatch.setattr(sc_mod, "SNAPSHOT_DIR", tmp_path, raising=False)

    # pre-create two snapshots
    state = LoopState()
    dump_state(state, session_id="sess", iteration=1, base_dir=tmp_path)
    dump_state(state, session_id="sess", iteration=2, base_dir=tmp_path)

    from vulpcode.commands.snapshot_cmd import SnapshotCommand

    agent = MagicMock()
    agent.session_id = "sess"

    printed: list[str] = []
    repl = MagicMock()
    repl.agent = agent
    repl.renderer.console.print = lambda msg: printed.append(str(msg))

    cmd = SnapshotCommand()
    await cmd.run(repl, "list")

    assert len([p for p in printed if "iter_" in p]) == 2
