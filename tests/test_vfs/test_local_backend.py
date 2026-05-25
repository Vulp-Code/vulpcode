"""Tests for LocalBackend: CRUD, glob, walk."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from vulpcode.vfs.local import LocalBackend
from vulpcode.vfs.protocol import VFSStat


@pytest.fixture()
def vfs(tmp_path: Path) -> LocalBackend:
    return LocalBackend()


def test_write_and_read_text(vfs: LocalBackend, tmp_path: Path) -> None:
    p = str(tmp_path / "hello.txt")
    size = vfs.write_text(p, "hello world")
    assert size > 0
    assert vfs.read_text(p) == "hello world"


def test_write_and_read_bytes(vfs: LocalBackend, tmp_path: Path) -> None:
    p = str(tmp_path / "data.bin")
    data = b"\x00\x01\x02\x03"
    size = vfs.write_bytes(p, data)
    assert size == 4
    assert vfs.read_bytes(p) == data


def test_exists(vfs: LocalBackend, tmp_path: Path) -> None:
    p = str(tmp_path / "x.txt")
    assert not vfs.exists(p)
    vfs.write_text(p, "")
    assert vfs.exists(p)


def test_is_file_is_dir(vfs: LocalBackend, tmp_path: Path) -> None:
    f = str(tmp_path / "f.txt")
    vfs.write_text(f, "data")
    assert vfs.is_file(f)
    assert not vfs.is_dir(f)
    assert vfs.is_dir(str(tmp_path))
    assert not vfs.is_file(str(tmp_path))


def test_list_dir(vfs: LocalBackend, tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    entries = vfs.list_dir(str(tmp_path))
    names = {Path(e).name for e in entries}
    assert names == {"a.txt", "b.txt"}


def test_remove(vfs: LocalBackend, tmp_path: Path) -> None:
    p = str(tmp_path / "del.txt")
    vfs.write_text(p, "bye")
    assert vfs.exists(p)
    vfs.remove(p)
    assert not vfs.exists(p)


def test_rename(vfs: LocalBackend, tmp_path: Path) -> None:
    src = str(tmp_path / "src.txt")
    dst = str(tmp_path / "dst.txt")
    vfs.write_text(src, "content")
    vfs.rename(src, dst)
    assert not vfs.exists(src)
    assert vfs.read_text(dst) == "content"


def test_stat(vfs: LocalBackend, tmp_path: Path) -> None:
    p = str(tmp_path / "s.txt")
    vfs.write_text(p, "hello")
    st = vfs.stat(p)
    assert isinstance(st, VFSStat)
    assert st.size == 5
    assert st.mtime > 0
    assert st.is_dir is False


def test_glob(vfs: LocalBackend, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "c.txt").write_text("")
    matches = vfs.glob("*.py", root=str(tmp_path))
    names = {Path(m).name for m in matches}
    assert names == {"a.py", "b.py"}


def test_walk(vfs: LocalBackend, tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.txt").write_text("")
    (tmp_path / "top.txt").write_text("")
    all_files: list[str] = []
    for dirpath, _, filenames in vfs.walk(str(tmp_path)):
        for f in filenames:
            all_files.append(os.path.join(dirpath, f))
    names = {Path(f).name for f in all_files}
    assert "top.txt" in names
    assert "deep.txt" in names


def test_write_creates_parents(vfs: LocalBackend, tmp_path: Path) -> None:
    p = str(tmp_path / "a" / "b" / "c.txt")
    vfs.write_text(p, "nested")
    assert vfs.read_text(p) == "nested"
