"""Tests for the Retrieve tool."""
import pytest

import vulpcode.tools  # noqa: F401  (ensures tools registered)
from vulpcode.providers._content_store import get_default_store
from vulpcode.tools import get_tool


@pytest.fixture(autouse=True)
def _clear_store():
    store = get_default_store()
    store.clear()
    yield
    store.clear()


@pytest.mark.asyncio
async def test_unknown_cache_id_is_error():
    cls = get_tool("Retrieve")
    res = await cls().run(cls.Input(cache_id="missing"))
    assert res.is_error
    assert "not found" in (res.error or "")
    assert "cache is empty" in (res.error or "")


@pytest.mark.asyncio
async def test_unknown_cache_id_lists_available():
    store = get_default_store()
    store.put("tt-a", "Read", "x")
    store.put("tt-b", "Read", "y")
    cls = get_tool("Retrieve")
    res = await cls().run(cls.Input(cache_id="nope"))
    assert res.is_error
    err = res.error or ""
    assert "tt-a" in err
    assert "tt-b" in err


@pytest.mark.asyncio
async def test_default_slice_returns_first_lines():
    store = get_default_store()
    body = "\n".join(f"line {i}" for i in range(1, 21))
    store.put("tt-1", "Read", body)
    cls = get_tool("Retrieve")
    res = await cls().run(cls.Input(cache_id="tt-1"))
    assert "1: line 1" in res.output
    assert "20: line 20" in res.output
    assert res.metadata["total_lines"] == 20


@pytest.mark.asyncio
async def test_default_slice_caps_at_max_output_lines():
    from vulpcode.tools.retrieve import _MAX_OUTPUT_LINES

    store = get_default_store()
    body = "\n".join(f"line {i}" for i in range(1, 1001))
    store.put("tt-1", "Read", body)
    cls = get_tool("Retrieve")
    res = await cls().run(cls.Input(cache_id="tt-1"))
    assert res.metadata["lines_returned"] == _MAX_OUTPUT_LINES
    assert f"showing first {_MAX_OUTPUT_LINES} of 1000" in res.output


@pytest.mark.asyncio
async def test_slice_by_line_range():
    store = get_default_store()
    body = "\n".join(f"L{i}" for i in range(1, 101))
    store.put("tt-1", "Read", body)
    cls = get_tool("Retrieve")
    res = await cls().run(cls.Input(cache_id="tt-1", start_line=10, end_line=15))
    lines = res.output.splitlines()
    assert lines[0] == "10: L10"
    assert lines[-1] == "15: L15"
    assert res.metadata["lines_returned"] == 6


@pytest.mark.asyncio
async def test_slice_by_line_range_with_only_start():
    store = get_default_store()
    body = "\n".join(f"L{i}" for i in range(1, 201))
    store.put("tt-1", "Read", body)
    cls = get_tool("Retrieve")
    res = await cls().run(cls.Input(cache_id="tt-1", start_line=50))
    # Default end is start + 100 - 1 = 149
    assert "50: L50" in res.output
    assert "149: L149" in res.output


@pytest.mark.asyncio
async def test_slice_by_line_start_beyond_total():
    store = get_default_store()
    body = "one\ntwo\nthree"
    store.put("tt-1", "Read", body)
    cls = get_tool("Retrieve")
    res = await cls().run(cls.Input(cache_id="tt-1", start_line=99))
    assert "exceeds total" in res.output


@pytest.mark.asyncio
async def test_slice_by_pattern():
    store = get_default_store()
    body = (
        "import foo\n"
        "import bar\n"
        "\n"
        "def hello():\n"
        "    pass\n"
        "\n"
        "class Widget:\n"
        "    def m(self): pass\n"
        "\n"
        "class Sprocket:\n"
        "    pass\n"
    )
    store.put("tt-1", "Read", body)
    cls = get_tool("Retrieve")
    res = await cls().run(cls.Input(cache_id="tt-1", pattern=r"^class "))
    assert "class Widget:" in res.output
    assert "class Sprocket:" in res.output
    assert res.metadata["matches"] == 2


@pytest.mark.asyncio
async def test_slice_by_pattern_with_context():
    store = get_default_store()
    body = "\n".join(f"L{i}" for i in range(1, 21))
    store.put("tt-1", "Read", body)
    cls = get_tool("Retrieve")
    res = await cls().run(
        cls.Input(cache_id="tt-1", pattern=r"^L10$", context_lines=2)
    )
    out = res.output
    assert "8: L8" in out
    assert "9: L9" in out
    assert "10: L10" in out
    assert "11: L11" in out
    assert "12: L12" in out
    assert "7: L7" not in out
    assert "13: L13" not in out


@pytest.mark.asyncio
async def test_slice_by_pattern_no_match():
    store = get_default_store()
    store.put("tt-1", "Read", "a\nb\nc")
    cls = get_tool("Retrieve")
    res = await cls().run(cls.Input(cache_id="tt-1", pattern="zzzzz"))
    assert res.metadata["matches"] == 0
    assert "No matches" in res.output


@pytest.mark.asyncio
async def test_slice_by_pattern_invalid_regex():
    store = get_default_store()
    store.put("tt-1", "Read", "a\nb")
    cls = get_tool("Retrieve")
    res = await cls().run(cls.Input(cache_id="tt-1", pattern="("))
    assert res.is_error
    assert "Invalid regex" in (res.error or "")


@pytest.mark.asyncio
async def test_pattern_case_insensitive_via_alias():
    store = get_default_store()
    store.put("tt-1", "Read", "Hello\nWORLD\nfoo")
    cls = get_tool("Retrieve")
    # Use the alias "-i" since that's how the schema exposes it externally.
    res = await cls().run(cls.Input.model_validate(
        {"cache_id": "tt-1", "pattern": "hello", "-i": True}
    ))
    assert "Hello" in res.output


def test_retrieve_does_not_require_confirm():
    cls = get_tool("Retrieve")
    assert cls._requires_confirm is False
