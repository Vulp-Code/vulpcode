"""Tests for JailBackend: operations inside and outside the jail."""
from __future__ import annotations

from pathlib import Path

import pytest

from vulpcode.vfs.jail import JailBackend
from vulpcode.vfs.protocol import VFSError


@pytest.fixture()
def jail(tmp_path: Path) -> JailBackend:
    return JailBackend(str(tmp_path))


def test_write_and_read_inside_jail(jail: JailBackend, tmp_path: Path) -> None:
    p = str(tmp_path / "file.txt")
    jail.write_text(p, "hello")
    assert jail.read_text(p) == "hello"


def test_relative_path_resolves_inside_jail(jail: JailBackend, tmp_path: Path) -> None:
    jail.write_text(str(tmp_path / "rel.txt"), "data")
    assert jail.read_text("rel.txt") == "data"


def test_read_escape_raises_vfs_error(jail: JailBackend, tmp_path: Path) -> None:
    escape = str(tmp_path / ".." / ".." / "etc" / "passwd")
    with pytest.raises(VFSError, match="escapes jail"):
        jail.read_text(escape)


def test_traversal_escape_raises_vfs_error(jail: JailBackend) -> None:
    with pytest.raises(VFSError, match="escapes jail"):
        jail.read_text("../../etc/passwd")


def test_write_escape_raises_vfs_error(jail: JailBackend) -> None:
    with pytest.raises(VFSError, match="escapes jail"):
        jail.write_text("../../tmp/evil.txt", "bad")


def test_rename_src_outside_jail_raises_vfs_error(jail: JailBackend, tmp_path: Path) -> None:
    outside = str(tmp_path / ".." / "ghost.txt")
    inside = str(tmp_path / "ok.txt")
    with pytest.raises(VFSError, match="escapes jail"):
        jail.rename(outside, inside)


def test_rename_dst_outside_jail_raises_vfs_error(jail: JailBackend, tmp_path: Path) -> None:
    inside = str(tmp_path / "ok.txt")
    jail.write_text(inside, "data")
    outside = str(tmp_path / ".." / "bad.txt")
    with pytest.raises(VFSError, match="escapes jail"):
        jail.rename(inside, outside)


def test_glob_returns_only_jail_matches(jail: JailBackend, tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text("")
    (tmp_path / "good2.py").write_text("")
    matches = jail.glob("*.py", root=str(tmp_path))
    for m in matches:
        assert str(tmp_path) in m


def test_exists_outside_jail_returns_false(jail: JailBackend, tmp_path: Path) -> None:
    outside = str(tmp_path / ".." / "anything")
    assert jail.exists(outside) is False


def test_is_file_inside_jail(jail: JailBackend, tmp_path: Path) -> None:
    p = str(tmp_path / "f.txt")
    jail.write_text(p, "x")
    assert jail.is_file(p) is True
    assert jail.is_dir(str(tmp_path)) is True


def test_list_dir_inside_jail(jail: JailBackend, tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    entries = jail.list_dir(str(tmp_path))
    names = {Path(e).name for e in entries}
    assert "a.txt" in names


def test_stat_inside_jail(jail: JailBackend, tmp_path: Path) -> None:
    p = str(tmp_path / "s.txt")
    jail.write_text(p, "hi")
    st = jail.stat(p)
    assert st.size == 2


def test_walk_stays_inside_jail(jail: JailBackend, tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "f.txt").write_text("")
    all_paths: list[str] = []
    for dirpath, _, filenames in jail.walk(str(tmp_path)):
        for fn in filenames:
            import os
            all_paths.append(os.path.join(dirpath, fn))
    for p in all_paths:
        assert str(tmp_path) in p
