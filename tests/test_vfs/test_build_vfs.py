"""Tests for build_vfs() factory function."""
from __future__ import annotations

from pathlib import Path

import pytest

from vulpcode.vfs import build_vfs
from vulpcode.vfs.jail import JailBackend
from vulpcode.vfs.local import LocalBackend
from vulpcode.vfs.sandbox import SandboxBackend


def test_build_vfs_default_returns_local_backend() -> None:
    vfs = build_vfs()
    assert isinstance(vfs, LocalBackend)
    assert vfs.name == "local"


def test_build_vfs_explicit_local() -> None:
    vfs = build_vfs({"backend": "local"})
    assert isinstance(vfs, LocalBackend)


def test_build_vfs_jail_without_root_raises_error() -> None:
    with pytest.raises(ValueError, match="jail_root"):
        build_vfs({"backend": "jail"})


def test_build_vfs_jail_empty_root_raises_error() -> None:
    with pytest.raises(ValueError, match="jail_root"):
        build_vfs({"backend": "jail", "jail_root": ""})


def test_build_vfs_jail_with_root(tmp_path: Path) -> None:
    vfs = build_vfs({"backend": "jail", "jail_root": str(tmp_path)})
    assert isinstance(vfs, JailBackend)
    assert vfs.name == "jail"


def test_build_vfs_sandbox() -> None:
    vfs = build_vfs({"backend": "sandbox"})
    assert isinstance(vfs, SandboxBackend)
    assert vfs.name == "sandbox"


def test_build_vfs_unknown_backend_raises_error() -> None:
    with pytest.raises(ValueError, match="Unknown vfs backend"):
        build_vfs({"backend": "unknown"})


def test_build_vfs_unknown_backend_lists_options() -> None:
    with pytest.raises(ValueError, match="local"):
        build_vfs({"backend": "doesnotexist"})


def test_build_vfs_none_config_returns_local() -> None:
    vfs = build_vfs(None)
    assert isinstance(vfs, LocalBackend)
