"""Snapshot/restore for LoopState: JSON-based foundation for crash recovery."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vulpcode.harness.state import LoopState

SNAPSHOT_DIR: Path = Path.home() / ".vulpcode" / "snapshots"


def dump_state(
    state: "LoopState",
    *,
    session_id: str,
    iteration: int,
    base_dir: Path | None = None,
) -> Path:
    """Serialize state to <base_dir>/<session_id>/iter_<N>.json.

    Uses atomic write (tmp + rename). Returns the path written.
    Provider is NOT serialized — only messages, usage, iteration, metadata.
    """
    from vulpcode.harness.state import STATE_SCHEMA_VERSION

    dest_dir = (base_dir or SNAPSHOT_DIR) / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    payload: dict = {
        "schema_version": STATE_SCHEMA_VERSION,
        "session_id": session_id,
        "iteration": iteration,
        "messages": [m.model_dump() for m in state.messages],
        "usage": state.usage.model_dump(),
        "metadata": dict(state.metadata),
    }

    path = dest_dir / f"iter_{iteration}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.rename(path)
    return path


def load_state(path: Path) -> "LoopState":
    """Deserialize a snapshot file into a LoopState.

    Raises ValueError if the schema_version cannot be migrated.
    """
    from vulpcode.harness.state import STATE_SCHEMA_VERSION, StateMetadata, LoopState
    from vulpcode.providers.base import Message, Usage

    data = json.loads(path.read_text(encoding="utf-8"))
    schema_ver = data.get("schema_version", 1)
    if schema_ver != STATE_SCHEMA_VERSION:
        data = _migrate(data, schema_ver, STATE_SCHEMA_VERSION)

    messages = [Message.model_validate(m) for m in data.get("messages", [])]
    usage = Usage.model_validate(data.get("usage", {}))
    metadata: StateMetadata = StateMetadata(**data.get("metadata", {}))  # type: ignore[misc]

    return LoopState(
        messages=messages,
        usage=usage,
        iteration=data.get("iteration", 0),
        metadata=metadata,
        version=STATE_SCHEMA_VERSION,
    )


def latest_snapshot(session_id: str, base_dir: Path | None = None) -> Path | None:
    """Return the snapshot with the highest iteration for session_id, or None."""
    session_dir = (base_dir or SNAPSHOT_DIR) / session_id
    if not session_dir.exists():
        return None
    candidates = list(session_dir.glob("iter_*.json"))
    if not candidates:
        return None

    def _iter_num(p: Path) -> int:
        try:
            return int(p.stem.split("_", 1)[1])
        except (IndexError, ValueError):
            return -1

    return max(candidates, key=_iter_num)


def _migrate(_data: dict, from_version: int, to_version: int) -> dict:
    """Migrate snapshot data between schema versions.

    Currently raises for any version mismatch. Add cases here when bumping
    STATE_SCHEMA_VERSION.
    """
    raise ValueError(
        f"Cannot migrate snapshot schema {from_version} → {to_version}. "
        "No migration path defined. See harness/snapshot.py::_migrate."
    )
