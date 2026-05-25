"""JailBackend: chroot-like VFS that rejects paths escaping a root directory."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator

from vulpcode.vfs.protocol import VFSError, VFSStat


def _within_jail(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


class JailBackend:
    """VFS backend that confines all operations to a directory root.

    Any path that resolves outside ``jail_root`` raises :class:`VFSError`.
    Useful for running the agent against a project directory in CI without
    risk of accidental writes to the host system.

    Note: Bash tool calls are NOT subject to jail restrictions — only VFS-aware
    file tools respect the jail boundary.
    """

    name = "jail"

    def __init__(self, jail_root: str) -> None:
        self._root = Path(jail_root).resolve()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        resolved = p.resolve() if p.is_absolute() else (self._root / path).resolve()
        if not _within_jail(resolved, self._root):
            raise VFSError(
                f"path escapes jail: {path!r} resolves outside {self._root}"
            )
        return resolved

    def read_text(self, path: str, *, encoding: str = "utf-8") -> str:
        return self._resolve(path).read_text(encoding=encoding)

    def read_bytes(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    def write_text(self, path: str, content: str, *, encoding: str = "utf-8") -> int:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=p.parent,
                prefix=f".{p.name}.",
                suffix=".tmp",
                delete=False,
                encoding=encoding,
            ) as tf:
                tf.write(content)
                tmp = Path(tf.name)
            os.replace(tmp, p)
        except VFSError:
            raise
        except BaseException:
            if tmp is not None and tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
        return p.stat().st_size

    def write_bytes(self, path: str, content: bytes) -> int:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=p.parent,
                prefix=f".{p.name}.",
                suffix=".tmp",
                delete=False,
            ) as tf:
                tf.write(content)
                tmp = Path(tf.name)
            os.replace(tmp, p)
        except VFSError:
            raise
        except BaseException:
            if tmp is not None and tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
        return p.stat().st_size

    def exists(self, path: str) -> bool:
        try:
            return self._resolve(path).exists()
        except VFSError:
            return False

    def is_file(self, path: str) -> bool:
        try:
            return self._resolve(path).is_file()
        except VFSError:
            return False

    def is_dir(self, path: str) -> bool:
        try:
            return self._resolve(path).is_dir()
        except VFSError:
            return False

    def list_dir(self, path: str) -> list[str]:
        return sorted(str(p) for p in self._resolve(path).iterdir())

    def remove(self, path: str) -> None:
        self._resolve(path).unlink()

    def rename(self, src: str, dst: str) -> None:
        self._resolve(src).rename(self._resolve(dst))

    def stat(self, path: str) -> VFSStat:
        p = self._resolve(path)
        s = p.stat()
        return VFSStat(size=s.st_size, mtime=s.st_mtime, is_dir=p.is_dir())

    def glob(self, pattern: str, *, root: str = ".") -> list[str]:
        try:
            base = self._resolve(root)
        except VFSError:
            return []
        result = []
        for p in base.glob(pattern):
            if _within_jail(p.resolve(), self._root):
                result.append(str(p))
        return result

    def walk(self, root: str) -> Iterator[tuple[str, list[str], list[str]]]:
        try:
            base = self._resolve(root)
        except VFSError:
            return
        for dirpath, dirnames, filenames in os.walk(str(base)):
            safe_dirs = [
                d
                for d in dirnames
                if _within_jail((Path(dirpath) / d).resolve(), self._root)
            ]
            dirnames[:] = safe_dirs
            yield dirpath, list(safe_dirs), filenames
