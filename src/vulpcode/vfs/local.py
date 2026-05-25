"""LocalBackend: thin wrapper over pathlib / os for the local filesystem."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator

from vulpcode.vfs.protocol import VFSStat


class LocalBackend:
    """VFS backend that delegates directly to the local filesystem."""

    name = "local"

    def read_text(self, path: str, *, encoding: str = "utf-8") -> str:
        return Path(path).read_text(encoding=encoding)

    def read_bytes(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def write_text(self, path: str, content: str, *, encoding: str = "utf-8") -> int:
        p = Path(path)
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
        except BaseException:
            if tmp is not None and tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
        return p.stat().st_size

    def write_bytes(self, path: str, content: bytes) -> int:
        p = Path(path)
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
        except BaseException:
            if tmp is not None and tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
        return p.stat().st_size

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def is_file(self, path: str) -> bool:
        return Path(path).is_file()

    def is_dir(self, path: str) -> bool:
        return Path(path).is_dir()

    def list_dir(self, path: str) -> list[str]:
        return sorted(str(p) for p in Path(path).iterdir())

    def remove(self, path: str) -> None:
        Path(path).unlink()

    def rename(self, src: str, dst: str) -> None:
        Path(src).rename(dst)

    def stat(self, path: str) -> VFSStat:
        p = Path(path)
        s = p.stat()
        return VFSStat(size=s.st_size, mtime=s.st_mtime, is_dir=p.is_dir())

    def glob(self, pattern: str, *, root: str = ".") -> list[str]:
        return [str(p) for p in Path(root).glob(pattern)]

    def walk(self, root: str) -> Iterator[tuple[str, list[str], list[str]]]:
        yield from os.walk(root)
