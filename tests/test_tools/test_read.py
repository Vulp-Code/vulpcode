"""Tests for the Read tool."""
from pathlib import Path

import pytest

import vulpcode.tools  # noqa: F401  ensure registry populated
from vulpcode.providers import ToolCall
from vulpcode.tools import TOOL_REGISTRY, execute_tool_call, get_tool
from vulpcode.tools.read import ReadTool


@pytest.fixture(autouse=True)
def _ensure_read_registered():
    # Other test modules may clear TOOL_REGISTRY between tests; re-insert
    # ReadTool so this module's tests see it regardless of run order.
    TOOL_REGISTRY["Read"] = ReadTool
    yield


@pytest.mark.asyncio
async def test_read_simple_file(tmp_path: Path):
    f = tmp_path / "hello.txt"
    f.write_text("line 1\nline 2\nline 3\n")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert res.is_error is False
    assert "1\tline 1" in res.output
    assert "3\tline 3" in res.output


@pytest.mark.asyncio
async def test_read_with_offset_limit(tmp_path: Path):
    f = tmp_path / "n.txt"
    f.write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f), offset=5, limit=2))
    assert "5\tline5" in res.output
    assert "6\tline6" in res.output
    assert "7\tline7" not in res.output


@pytest.mark.asyncio
async def test_read_missing_file(tmp_path: Path):
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(tmp_path / "nope")))
    assert res.is_error
    assert "does not exist" in (res.error or "")


@pytest.mark.asyncio
async def test_read_directory_is_error(tmp_path: Path):
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(tmp_path)))
    assert res.is_error


@pytest.mark.asyncio
async def test_read_binary_file_rejected(tmp_path: Path):
    f = tmp_path / "bin.dat"
    f.write_bytes(b"hello\x00world")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert res.is_error
    assert "binary" in (res.error or "").lower()


@pytest.mark.asyncio
async def test_read_empty_file(tmp_path: Path):
    f = tmp_path / "e.txt"
    f.write_text("")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert "empty" in res.output.lower()


@pytest.mark.asyncio
async def test_read_image_returns_metadata(tmp_path: Path):
    f = tmp_path / "img.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert res.is_error is False
    assert res.metadata.get("is_image") is True


@pytest.mark.asyncio
async def test_read_through_execute_tool_call(tmp_path: Path):
    f = tmp_path / "x.txt"
    f.write_text("ok\n")
    tc = ToolCall(id="1", name="Read", arguments={"file_path": str(f)})
    res = await execute_tool_call(tc)
    assert "1\tok" in res.output


@pytest.mark.asyncio
async def test_read_tilde_expansion(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "home.txt"
    target.write_text("hi\n")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path="~/home.txt"))
    assert "1\thi" in res.output


@pytest.mark.asyncio
async def test_read_long_line_is_truncated(tmp_path: Path):
    f = tmp_path / "long.txt"
    f.write_text("x" * 2500 + "\n")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert res.is_error is False
    assert "[truncated]" in res.output


@pytest.mark.asyncio
async def test_read_truncated_continuation_hint(tmp_path: Path):
    f = tmp_path / "many.txt"
    f.write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f), limit=3))
    assert "more lines" in res.output
    assert "offset=4" in res.output
