"""SandboxBackend: stub for future container/remote execution integration.

This backend is a placeholder. A future implementation will delegate all file
operations to an isolated execution environment — Docker, Firecracker, or a
remote sandbox API. See ``docs/harness/vfs.md`` for the roadmap.

To implement a real sandbox backend:
1. Subclass or replace ``SandboxBackend``.
2. Wire API calls (container exec / HTTP) into each method.
3. Register the backend name in ``vulpcode.vfs.build_vfs``.
"""
from __future__ import annotations

from typing import Iterator

from vulpcode.vfs.protocol import VFSStat

_MSG = (
    "SandboxBackend is not yet implemented. "
    "Future versions will delegate to Docker/Firecracker or a remote sandbox. "
    "See docs/harness/vfs.md for the roadmap."
)


class SandboxBackend:
    """Stub VFS backend — all methods raise NotImplementedError."""

    name = "sandbox"

    def read_text(self, path: str, *, encoding: str = "utf-8") -> str:
        raise NotImplementedError(_MSG)

    def read_bytes(self, path: str) -> bytes:
        raise NotImplementedError(_MSG)

    def write_text(self, path: str, content: str, *, encoding: str = "utf-8") -> int:
        raise NotImplementedError(_MSG)

    def write_bytes(self, path: str, content: bytes) -> int:
        raise NotImplementedError(_MSG)

    def exists(self, path: str) -> bool:
        raise NotImplementedError(_MSG)

    def is_file(self, path: str) -> bool:
        raise NotImplementedError(_MSG)

    def is_dir(self, path: str) -> bool:
        raise NotImplementedError(_MSG)

    def list_dir(self, path: str) -> list[str]:
        raise NotImplementedError(_MSG)

    def remove(self, path: str) -> None:
        raise NotImplementedError(_MSG)

    def rename(self, src: str, dst: str) -> None:
        raise NotImplementedError(_MSG)

    def stat(self, path: str) -> VFSStat:
        raise NotImplementedError(_MSG)

    def glob(self, pattern: str, *, root: str = ".") -> list[str]:
        raise NotImplementedError(_MSG)

    def walk(self, root: str) -> Iterator[tuple[str, list[str], list[str]]]:
        raise NotImplementedError(_MSG)
