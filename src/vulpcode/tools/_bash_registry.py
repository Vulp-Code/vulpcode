"""Shared registry for background bash processes."""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class BackgroundProcess:
    bash_id: str
    command: str
    process: asyncio.subprocess.Process
    started_at: float
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)
    exit_code: int | None = None
    stdout_offset: int = 0
    stderr_offset: int = 0
    _reader_task: asyncio.Task | None = None


_REGISTRY: dict[str, BackgroundProcess] = {}


def new_id() -> str:
    return f"bash_{uuid.uuid4().hex[:8]}"


def register(proc: BackgroundProcess) -> None:
    _REGISTRY[proc.bash_id] = proc


def get(bash_id: str) -> BackgroundProcess | None:
    return _REGISTRY.get(bash_id)


def list_all() -> list[BackgroundProcess]:
    return list(_REGISTRY.values())


def remove(bash_id: str) -> None:
    _REGISTRY.pop(bash_id, None)


def now() -> float:
    return time.time()
