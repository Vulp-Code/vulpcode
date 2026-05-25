"""Tests for the ContextHub middleware (FASE_04)."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pytest

from vulpcode.harness.context_hub import ContextHub, ContextHubConfig
from vulpcode.providers.base import ToolCall
from vulpcode.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hub(tmp_path: Path, **kwargs) -> ContextHub:
    """Build a ContextHub with storage_dir pointing at tmp_path."""
    cfg = ContextHubConfig(
        enabled=True,
        threshold_chars=kwargs.get("threshold_chars", 4000),
        preview_head_lines=kwargs.get("preview_head_lines", 30),
        preview_tail_lines=kwargs.get("preview_tail_lines", 10),
        storage_dir=tmp_path / "handles",
        keep_handles_days=kwargs.get("keep_handles_days", 7),
    )
    return ContextHub(cfg, session_id="test-session")


def _make_call(name: str = "Bash") -> ToolCall:
    return ToolCall(id="tc1", name=name, arguments={})


def _make_result(content: str, is_error: bool = False) -> ToolResult:
    return ToolResult(output=content, is_error=is_error)


def _big_content(n_lines: int = 500, line_len: int = 80) -> str:
    return "\n".join(f"line {i:04d}: " + "x" * line_len for i in range(n_lines))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_op_below_threshold(tmp_path: Path) -> None:
    """Small outputs pass through unchanged."""
    hub = _make_hub(tmp_path)
    content = "a" * 1000
    result = _make_result(content)
    returned = hub(None, call=_make_call(), result=result)
    assert returned is not None
    assert returned.output == content
    assert not returned.is_error


def test_offloads_above_threshold(tmp_path: Path) -> None:
    """Large outputs are replaced with a handle preview."""
    hub = _make_hub(tmp_path)
    content = _big_content(200)
    result = _make_result(content)
    returned = hub(None, call=_make_call("Read"), result=result)
    assert returned is not None
    assert "OFFLOADED" in returned.output
    assert "handle://" in returned.output
    assert "HandleRead" in returned.output
    assert returned.output != content


def test_handle_file_exists_and_matches(tmp_path: Path) -> None:
    """The file written to disk matches the original content exactly."""
    hub = _make_hub(tmp_path)
    content = _big_content(300)
    result = _make_result(content)
    returned = hub(None, call=_make_call("Bash"), result=result)
    assert returned is not None
    filename = returned.metadata["offloaded_to"]
    handle_path = hub.dir / filename
    assert handle_path.exists()
    assert handle_path.read_text(encoding="utf-8") == content


def test_filename_pattern(tmp_path: Path) -> None:
    """Filename matches YYYY-MM-DD_HH-MM-SS_<tool>_<6hex>.txt."""
    hub = _make_hub(tmp_path)
    content = _big_content(200)
    result = _make_result(content)
    returned = hub(None, call=_make_call("Grep"), result=result)
    assert returned is not None
    filename = returned.metadata["offloaded_to"]
    pattern = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_Grep_[0-9a-f]{6}\.txt$"
    assert re.match(pattern, filename), f"unexpected filename: {filename!r}"


def test_preview_format_head_and_tail(tmp_path: Path) -> None:
    """Preview contains head + tail sections with Unicode separator lines."""
    hub = _make_hub(tmp_path, preview_head_lines=5, preview_tail_lines=3, threshold_chars=100)
    lines = [f"line_{i}" for i in range(20)]
    content = "\n".join(lines)
    result = _make_result(content)
    returned = hub(None, call=_make_call("Bash"), result=result)
    assert returned is not None
    preview = returned.output
    sep = "─" * 25
    assert sep in preview
    # head section
    assert "PREVIEW (first 5 lines):" in preview
    assert "line_0" in preview
    # tail section
    assert "PREVIEW (last 3 lines):" in preview
    assert "line_19" in preview


def test_error_results_not_offloaded(tmp_path: Path) -> None:
    """Results with is_error=True are never offloaded, even when large."""
    hub = _make_hub(tmp_path)
    content = _big_content(500)
    result = ToolResult(output=content, is_error=True)
    returned = hub(None, call=_make_call("Bash"), result=result)
    assert returned is not None
    assert returned.output == content
    assert returned.is_error is True
    # No files should have been created.
    assert list(hub.dir.iterdir()) == []


def test_handle_read_full(tmp_path: Path) -> None:
    """read_slice with lines='all' returns the full original content."""
    hub = _make_hub(tmp_path)
    content = _big_content(200)
    filename = hub.offload(tool_name="Bash", content=content)
    result = hub.read_slice(filename, lines="all", grep=None, max_chars=50000)
    assert result == content


def test_handle_read_slice(tmp_path: Path) -> None:
    """read_slice with lines='100-200' returns exactly 101 lines."""
    hub = _make_hub(tmp_path)
    content = "\n".join(f"L{i}" for i in range(1, 501))
    filename = hub.offload(tool_name="Bash", content=content)
    result = hub.read_slice(filename, lines="100-200", grep=None, max_chars=50000)
    result_lines = result.splitlines()
    assert len(result_lines) == 101
    assert result_lines[0] == "L100"
    assert result_lines[-1] == "L200"


def test_handle_read_grep(tmp_path: Path) -> None:
    """read_slice with grep='error' returns only matching lines."""
    hub = _make_hub(tmp_path)
    lines_data = ["ok line", "error found here", "another ok", "error again", "fine"]
    content = "\n".join(lines_data)
    filename = hub.offload(tool_name="Bash", content=content)
    result = hub.read_slice(filename, lines="all", grep="error", max_chars=50000)
    result_lines = result.splitlines()
    assert len(result_lines) == 2
    assert all("error" in ln for ln in result_lines)


def test_handle_read_max_chars_truncates(tmp_path: Path) -> None:
    """read_slice truncates output to max_chars and appends a truncation marker."""
    hub = _make_hub(tmp_path)
    content = "x" * 10000
    filename = hub.offload(tool_name="Bash", content=content)
    result = hub.read_slice(filename, lines="all", grep=None, max_chars=500)
    assert len(result) > 500  # marker is appended
    assert "TRUNCATED" in result
    assert result.startswith("x" * 500)


def test_handle_read_path_traversal_blocked(tmp_path: Path) -> None:
    """Handles with path traversal components are rejected with is_error=True."""
    from vulpcode.tools.handle import HandleReadTool, set_hub

    hub = _make_hub(tmp_path)
    set_hub(hub)

    tool = HandleReadTool()
    inp = HandleReadTool.Input(handle="../etc/passwd", lines="all")

    import asyncio

    result = asyncio.run(tool.run(inp))
    assert result.is_error is True
    assert "invalid handle" in (result.error or "").lower()

    # Clean up module-level hub reference.
    set_hub(None)


def test_cleanup_removes_old_files(tmp_path: Path) -> None:
    """Files older than keep_handles_days are deleted when ContextHub is initialised."""
    handles_dir = tmp_path / "handles" / "old-session"
    handles_dir.mkdir(parents=True)

    old_file = handles_dir / "2020-01-01_00-00-00_Bash_aabbcc.txt"
    old_file.write_text("old content", encoding="utf-8")

    # Back-date the file to 10 days ago.
    old_mtime = time.time() - 10 * 86400
    os.utime(old_file, (old_mtime, old_mtime))

    # Creating a ContextHub with keep_handles_days=7 should remove the file.
    _make_hub(tmp_path, keep_handles_days=7)

    assert not old_file.exists(), "stale handle file should have been removed"


# ---------------------------------------------------------------------------
# Config / middleware wiring
# ---------------------------------------------------------------------------


def test_context_hub_config_defaults() -> None:
    """ContextHubConfig has sensible defaults."""
    cfg = ContextHubConfig()
    assert cfg.enabled is False
    assert cfg.threshold_chars == 4000
    assert cfg.preview_head_lines == 30
    assert cfg.preview_tail_lines == 10
    assert cfg.keep_handles_days == 7


def test_register_default_middleware_wires_hub(tmp_path: Path) -> None:
    """register_default_middleware registers context_hub on after_tool_call."""
    from vulpcode.harness import HookBus, register_default_middleware

    bus = HookBus()
    config = {
        "middleware": {
            "context_hub": {
                "enabled": True,
                "threshold_chars": 100,
                "storage_dir": str(tmp_path / "handles"),
            }
        }
    }
    register_default_middleware(bus, config, session_id="sess-abc")
    desc = bus.describe()
    assert "after_tool_call" in desc
    names = [h["name"] for h in desc["after_tool_call"]]
    assert "context_hub" in names


def test_clip_registered_before_hub(tmp_path: Path) -> None:
    """Overflow clip is registered before context hub in after_tool_call."""
    from vulpcode.harness import HookBus, register_default_middleware

    bus = HookBus()
    config = {
        "middleware": {
            "overflow_clip": {"enabled": True},
            "context_hub": {
                "enabled": True,
                "storage_dir": str(tmp_path / "handles"),
            },
        }
    }
    register_default_middleware(bus, config, session_id="sess-order")
    desc = bus.describe()
    names = [h["name"] for h in desc.get("after_tool_call", [])]
    assert names.index("overflow_clip") < names.index("context_hub")
