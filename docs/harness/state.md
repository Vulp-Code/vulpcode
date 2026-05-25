# Harness State

> **Note**: Full documentation will be written in FASE_09.

## Overview

`LoopState` is the canonical state object passed to every middleware hook during
the agent loop. It lives in `vulpcode.harness.state`.

## Reducers

Each field in `LoopState` has an associated **reducer** declared via `Annotated`:

- `replace` — new value replaces old (default)
- `append_messages` — concatenates message lists
- `evict_messages` — removes messages by index
- `merge_metadata` — shallow-merges dicts (new keys win)

Use `state.apply(**updates)` to produce a new state through reducers.
Direct mutation (`state.messages.append(...)`) is allowed for backward compat.

## StateMetadata

`StateMetadata` is a `TypedDict` with `total=False` (all keys optional).
Declare new middleware keys here to get IDE autocompletion and mypy coverage.

```python
class StateMetadata(TypedDict, total=False):
    skills_injected: bool
    active_skill_tools_allow: list[str] | None
    last_summarization_iteration: int
    last_block_message: str
    handle_ids_emitted_this_turn: list[str]
```

## Snapshots

```python
from vulpcode.harness.snapshot import dump_state, load_state, latest_snapshot

path = dump_state(state, session_id="my-session", iteration=42)
restored = load_state(path)
```

Snapshots are stored under `~/.vulpcode/snapshots/<session_id>/iter_<N>.json`.
The `Provider` is **not** serialized — you must reinject it after a restore.

## Schema versioning

`STATE_SCHEMA_VERSION = 1`. When the schema changes, bump the constant and add
a migration case in `harness/snapshot.py::_migrate`.
