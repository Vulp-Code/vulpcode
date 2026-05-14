"""Session persistence (~/.vulpcode/sessions/)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from vulpcode.agent import Agent


_VERSION = 1


def _sessions_dir(scope: Path | None = None) -> Path:
    base = scope or (Path.home() / ".vulpcode" / "sessions")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _safe_name(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_"))
    return safe or "default"


def _session_path(name: str, scope: Path | None = None) -> Path:
    return _sessions_dir(scope) / f"{_safe_name(name)}.json"


def save_session(name: str, agent: "Agent", *, scope: Path | None = None) -> Path:
    """Persist an agent's conversation state to a JSON file.

    The payload includes the provider name, model, system prompt, full
    message history and accumulated session usage. The write is atomic
    (``.tmp`` then ``rename``) so a crash never leaves a partial file.

    Args:
        name: Logical session name. Non-alphanumeric characters (other
            than ``-`` and ``_``) are stripped to build the filename.
        agent: The [`Agent`][vulpcode.agent.Agent] whose state is being
            captured.
        scope: Override the destination directory. Defaults to
            ``~/.vulpcode/sessions/``.

    Returns:
        The absolute path of the saved JSON file.
    """
    target = _session_path(name, scope)
    payload = {
        "version": _VERSION,
        "name": name,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "provider_name": getattr(agent.provider, "name", "unknown"),
        "model": agent.model,
        "system": agent.system,
        "messages": [m.model_dump() for m in agent._messages],
        "session_usage": (
            agent._session_usage.model_dump()
            if hasattr(agent, "_session_usage") and agent._session_usage is not None
            else None
        ),
    }
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return target


def load_session(name: str, agent: "Agent", *, scope: Path | None = None) -> None:
    """Restore a saved session into an existing agent (in place).

    Replaces the agent's ``system``, ``model``, ``_messages`` and (if
    available) ``_session_usage`` with the values from disk. The provider
    is **not** rebuilt — pair this with the same provider used to save
    the session, or rebuild your agent before calling it.

    Args:
        name: The session name passed to
            [`save_session`][vulpcode.session.save_session].
        agent: The agent that will receive the restored state.
        scope: Override the source directory. Defaults to
            ``~/.vulpcode/sessions/``.

    Raises:
        FileNotFoundError: If no file matches the requested name.
    """
    from vulpcode.providers.base import Message, Usage

    target = _session_path(name, scope)
    if not target.exists():
        raise FileNotFoundError(f"Session {name!r} not found at {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    agent.system = payload.get("system", agent.system)
    agent.model = payload.get("model", agent.model)
    agent._messages = [Message.model_validate(m) for m in payload.get("messages", [])]
    if hasattr(agent, "_session_usage") and payload.get("session_usage"):
        agent._session_usage = Usage.model_validate(payload["session_usage"])


def list_sessions(*, scope: Path | None = None) -> list[dict]:
    """Return all sessions in the directory, newest first.

    Each entry is a dict with the keys ``name``, ``saved_at``, ``messages``,
    ``model`` and ``path``. Files that fail to parse as JSON are silently
    skipped so a corrupt session never blocks the listing.

    Args:
        scope: Override the source directory. Defaults to
            ``~/.vulpcode/sessions/``.

    Returns:
        A list of metadata dicts ordered by file mtime (most recent first).
    """
    out: list[dict] = []
    for p in sorted(
        _sessions_dir(scope).glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append(
            {
                "name": payload.get("name", p.stem),
                "saved_at": payload.get("saved_at"),
                "messages": len(payload.get("messages", [])),
                "model": payload.get("model", ""),
                "path": str(p),
            }
        )
    return out


def latest_session_name(*, scope: Path | None = None) -> str | None:
    """Return the name of the most recently saved session, or ``None``.

    Used by the CLI ``--resume`` flag (without a name) to pick up where
    the user left off.

    Args:
        scope: Override the source directory. Defaults to
            ``~/.vulpcode/sessions/``.

    Returns:
        The session name if at least one valid session exists, else ``None``.
    """
    sessions = list_sessions(scope=scope)
    if not sessions:
        return None
    return sessions[0]["name"]


def delete_session(name: str, *, scope: Path | None = None) -> bool:
    """Delete a session file from disk.

    Args:
        name: The logical session name (same value passed to
            [`save_session`][vulpcode.session.save_session]).
        scope: Override the source directory. Defaults to
            ``~/.vulpcode/sessions/``.

    Returns:
        ``True`` if a file was removed, ``False`` if no matching session
        existed.
    """
    target = _session_path(name, scope)
    if not target.exists():
        return False
    target.unlink()
    return True
