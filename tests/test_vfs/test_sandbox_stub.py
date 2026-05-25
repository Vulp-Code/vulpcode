"""Tests for SandboxBackend: all methods must raise NotImplementedError."""
from __future__ import annotations

import pytest

from vulpcode.vfs.sandbox import SandboxBackend


@pytest.fixture()
def sb() -> SandboxBackend:
    return SandboxBackend()


def test_read_text_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.read_text("/any/path")


def test_read_bytes_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.read_bytes("/any/path")


def test_write_text_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.write_text("/any/path", "content")


def test_write_bytes_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.write_bytes("/any/path", b"data")


def test_exists_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.exists("/any/path")


def test_is_file_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.is_file("/any/path")


def test_is_dir_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.is_dir("/any/path")


def test_list_dir_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.list_dir("/any/path")


def test_remove_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.remove("/any/path")


def test_rename_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.rename("/src", "/dst")


def test_stat_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.stat("/any/path")


def test_glob_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        sb.glob("*.py")


def test_walk_not_implemented(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError):
        list(sb.walk("/any/root"))


def test_error_message_mentions_roadmap(sb: SandboxBackend) -> None:
    with pytest.raises(NotImplementedError, match="roadmap"):
        sb.read_text("/x")


def test_name_attribute(sb: SandboxBackend) -> None:
    assert sb.name == "sandbox"
