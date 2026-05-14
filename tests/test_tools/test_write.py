from pathlib import Path

import pytest

import vulpcode.tools  # noqa: F401  ensure registry populated
from vulpcode.tools import TOOL_REGISTRY, get_tool
from vulpcode.tools.write import WriteTool


@pytest.fixture(autouse=True)
def _ensure_write_registered():
    # Other test modules may clear TOOL_REGISTRY between tests; re-insert
    # WriteTool so this module's tests see it regardless of run order.
    TOOL_REGISTRY["Write"] = WriteTool
    yield


@pytest.mark.asyncio
async def test_write_creates_new_file(tmp_path: Path):
    cls = get_tool("Write")
    target = tmp_path / "subdir" / "out.txt"
    res = await cls().run(cls.Input(file_path=str(target), content="hello"))
    assert res.is_error is False
    assert target.read_text() == "hello"
    assert "5 bytes" in res.output
    assert str(target.resolve()) in res.output


@pytest.mark.asyncio
async def test_write_overwrites_existing(tmp_path: Path):
    cls = get_tool("Write")
    f = tmp_path / "x.txt"
    f.write_text("old")
    res = await cls().run(cls.Input(file_path=str(f), content="new"))
    assert res.is_error is False
    assert f.read_text() == "new"


@pytest.mark.asyncio
async def test_write_empty_content(tmp_path: Path):
    cls = get_tool("Write")
    f = tmp_path / "empty.txt"
    res = await cls().run(cls.Input(file_path=str(f), content=""))
    assert res.is_error is False
    assert f.exists()
    assert f.read_text() == ""
    assert "0 bytes" in res.output


@pytest.mark.asyncio
async def test_write_creates_parent_dirs(tmp_path: Path):
    cls = get_tool("Write")
    deep = tmp_path / "a" / "b" / "c" / "d.txt"
    res = await cls().run(cls.Input(file_path=str(deep), content="x"))
    assert res.is_error is False
    assert deep.exists()


@pytest.mark.asyncio
async def test_write_utf8_encoding(tmp_path: Path):
    cls = get_tool("Write")
    f = tmp_path / "utf8.txt"
    content = "olá mundo — ações 🦊"
    res = await cls().run(cls.Input(file_path=str(f), content=content))
    assert res.is_error is False
    assert f.read_text(encoding="utf-8") == content
    assert f.read_bytes() == content.encode("utf-8")


@pytest.mark.asyncio
async def test_write_returns_absolute_path_in_metadata(tmp_path: Path):
    cls = get_tool("Write")
    f = tmp_path / "meta.txt"
    res = await cls().run(cls.Input(file_path=str(f), content="data"))
    assert res.is_error is False
    assert res.metadata["file_path"] == str(f.resolve())
    assert res.metadata["size"] == 4
    assert res.metadata["created"] is True


def test_write_requires_confirm():
    cls = get_tool("Write")
    assert cls._requires_confirm is True
