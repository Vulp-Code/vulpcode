"""Session persistence (~/.vulpcode/sessions/)."""
from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vulpcode.agent import Agent

_VERSION = 1

_current_state: ContextVar[Any] = ContextVar("_current_state", default=None)
skill_registry: Any = None


def get_session_skill_registry() -> Any:
    return skill_registry


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
    out: list[dict] = []
    for p in sorted(_sessions_dir(scope).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({"name": payload.get("name", p.stem), "saved_at": payload.get("saved_at"),
                    "messages": len(payload.get("messages", [])), "model": payload.get("model", ""),
                    "path": str(p)})
    return out


def latest_session_name(*, scope: Path | None = None) -> str | None:
    sessions = list_sessions(scope=scope)
    return sessions[0]["name"] if sessions else None


def delete_session(name: str, *, scope: Path | None = None) -> bool:
    target = _session_path(name, scope)
    if not target.exists():
        return False
    target.unlink()
    return True
