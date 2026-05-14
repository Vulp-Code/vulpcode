from pathlib import Path

import pytest

import vulpcode.tools  # noqa: F401  (registers tools)
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_read_utf8_with_bom(tmp_path: Path):
    f = tmp_path / "bom.txt"
    f.write_bytes(b"\xef\xbb\xbfhello\n")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert res.is_error is False
    assert "hello" in res.output


@pytest.mark.asyncio
async def test_read_latin1_via_replace(tmp_path: Path):
    f = tmp_path / "lat.txt"
    f.write_bytes("café\n".encode("latin-1"))
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    # Decoded as utf-8 with replace; should not error and should not be empty
    assert res.is_error is False
    assert len(res.output) > 0


@pytest.mark.asyncio
async def test_read_utf16_with_bom(tmp_path: Path):
    f = tmp_path / "u16.txt"
    # UTF-16 LE BOM + payload. UTF-16 contains many NUL bytes for ASCII
    # text, so the Read tool's binary heuristic should flag it as binary
    # and return an error rather than garbage decoded output.
    f.write_bytes("hello world".encode("utf-16"))
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert res.is_error is True
    assert "binary" in (res.error or "").lower()


@pytest.mark.asyncio
async def test_read_pure_ascii_unchanged(tmp_path: Path):
    f = tmp_path / "plain.txt"
    f.write_bytes(b"line one\nline two\n")
    cls = get_tool("Read")
    res = await cls().run(cls.Input(file_path=str(f)))
    assert res.is_error is False
    assert "line one" in res.output
    assert "line two" in res.output
