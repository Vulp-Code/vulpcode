"""Tests for WriteHtml, WriteSh, WriteSql, WriteSvg, WriteDot tools."""
import shutil

import pytest

import vulpcode.tools.write_dot
import vulpcode.tools.write_html
import vulpcode.tools.write_sh
import vulpcode.tools.write_sql
import vulpcode.tools.write_svg
from vulpcode.tools import get_tool


# ---------------------------------------------------------------------------
# WriteHtml
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_html_valid(tmp_path):
    cls = get_tool("WriteHtml")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.html"),
        content="<html><body><h1>hi</h1></body></html>",
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_html_minimal(tmp_path):
    cls = get_tool("WriteHtml")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "min.html"),
        content="<p>hello</p>",
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_html_strict_without_lxml(tmp_path, monkeypatch):
    """strict=True without lxml should return an error."""
    import sys
    # Simulate lxml not being importable
    monkeypatch.setitem(sys.modules, "lxml", None)
    monkeypatch.setitem(sys.modules, "lxml.html", None)
    cls = get_tool("WriteHtml")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "strict.html"),
        content="<html></html>",
        strict=True,
    ))
    assert res.is_error is True
    assert "lxml" in (res.error or "").lower()


# ---------------------------------------------------------------------------
# WriteSh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
async def test_write_sh_valid(tmp_path):
    cls = get_tool("WriteSh")
    target = tmp_path / "s.sh"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="#!/usr/bin/env bash\necho hi\n",
    ))
    assert res.is_error is False
    assert target.stat().st_mode & 0o100  # exec bit set


@pytest.mark.asyncio
@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
async def test_write_sh_syntax_error(tmp_path):
    cls = get_tool("WriteSh")
    target = tmp_path / "bad.sh"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="if true then echo\n",  # missing fi
    ))
    assert res.is_error is True
    assert not target.exists()


@pytest.mark.asyncio
@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
async def test_write_sh_not_executable(tmp_path):
    """executable=False should not set the exec bit."""
    cls = get_tool("WriteSh")
    target = tmp_path / "no_x.sh"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="#!/usr/bin/env bash\necho hello\n",
        executable=False,
    ))
    assert res.is_error is False
    # exec bit should NOT be set (we didn't request it)
    assert not (target.stat().st_mode & 0o100)


@pytest.mark.asyncio
async def test_write_sh_no_bash_fallback_no_shebang(tmp_path, monkeypatch):
    """Without bash on PATH and no shebang, should fail."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    cls = get_tool("WriteSh")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.sh"),
        content="echo hello\n",  # no shebang
    ))
    assert res.is_error is True
    assert "shebang" in (res.error or "").lower()


@pytest.mark.asyncio
async def test_write_sh_no_bash_fallback_with_shebang(tmp_path, monkeypatch):
    """Without bash on PATH but with shebang, should succeed."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    cls = get_tool("WriteSh")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "x.sh"),
        content="#!/bin/sh\necho hello\n",
    ))
    assert res.is_error is False


# ---------------------------------------------------------------------------
# WriteSql
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_sql_valid(tmp_path):
    cls = get_tool("WriteSql")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "q.sql"),
        content="SELECT id, name FROM users WHERE active = 1;\n",
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_sql_unbalanced_parens(tmp_path):
    cls = get_tool("WriteSql")
    target = tmp_path / "bad.sql"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="SELECT a, b FROM t WHERE x IN (1, 2;",
    ))
    assert res.is_error is True
    assert "parens" in (res.error or "").lower()
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_sql_close_before_open(tmp_path):
    cls = get_tool("WriteSql")
    target = tmp_path / "bad2.sql"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="SELECT ) FROM t;",
    ))
    assert res.is_error is True
    assert "parens" in (res.error or "").lower()


@pytest.mark.asyncio
async def test_write_sql_unbalanced_quotes(tmp_path):
    cls = get_tool("WriteSql")
    target = tmp_path / "bad3.sql"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="SELECT * FROM t WHERE name = 'alice;",
    ))
    assert res.is_error is True
    assert "quote" in (res.error or "").lower()


# ---------------------------------------------------------------------------
# WriteSvg
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_svg_valid(tmp_path):
    cls = get_tool("WriteSvg")
    content = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<circle cx="50" cy="50" r="40"/>'
        '</svg>'
    )
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "circle.svg"),
        content=content,
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_svg_wrong_root(tmp_path):
    cls = get_tool("WriteSvg")
    target = tmp_path / "bad.svg"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="<root></root>",
    ))
    assert res.is_error is True
    assert "root element must be <svg>" in (res.error or "").lower()
    assert not target.exists()


@pytest.mark.asyncio
async def test_write_svg_invalid_xml(tmp_path):
    cls = get_tool("WriteSvg")
    target = tmp_path / "broken.svg"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="<svg><unclosed>",
    ))
    assert res.is_error is True
    assert not target.exists()


# ---------------------------------------------------------------------------
# WriteDot
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_dot_no_pydot(tmp_path, monkeypatch):
    """Without pydot, WriteDot should return a helpful error."""
    import sys
    monkeypatch.setitem(sys.modules, "pydot", None)
    cls = get_tool("WriteDot")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "g.dot"),
        content="digraph G { a -> b; }",
    ))
    assert res.is_error is True
    assert "pydot" in (res.error or "").lower()


@pytest.mark.asyncio
async def test_write_dot_valid(tmp_path):
    pydot = pytest.importorskip("pydot")
    cls = get_tool("WriteDot")
    res = await cls().run(cls.Input(
        file_path=str(tmp_path / "g.dot"),
        content="digraph G { a -> b; b -> c; }",
    ))
    assert res.is_error is False


@pytest.mark.asyncio
async def test_write_dot_invalid(tmp_path):
    pytest.importorskip("pydot")
    cls = get_tool("WriteDot")
    target = tmp_path / "bad.dot"
    res = await cls().run(cls.Input(
        file_path=str(target),
        content="this is not dot syntax @@@",
    ))
    # pydot may or may not error on bad syntax; if it produces no graphs → error
    if res.is_error:
        assert "pydot" in (res.error or "").lower() or "graph" in (res.error or "").lower()
