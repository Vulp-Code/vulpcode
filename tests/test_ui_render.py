"""Tests for UI renderer and themes."""
import io

from rich.console import Console

from vulpcode.providers.base import ToolCall, Usage
from vulpcode.tools.base import ToolResult
from vulpcode.ui import Renderer, Theme, get_theme


def make_renderer():
    buf = io.StringIO()
    console = Console(file=buf, width=80, force_terminal=False, color_system=None)
    return Renderer(console, get_theme("default")), buf


def test_get_theme_known():
    assert get_theme("default").name == "default"
    assert get_theme("monokai").name == "monokai"
    assert get_theme("light").name == "light"


def test_get_theme_fallback_to_default():
    assert get_theme("does-not-exist").name == "default"


def test_theme_is_frozen():
    t = get_theme("default")
    assert isinstance(t, Theme)
    try:
        t.primary = "red"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Theme should be frozen")


def test_render_text_chunk():
    r, buf = make_renderer()
    r.render_text_chunk("hello")
    assert "hello" in buf.getvalue()
    assert r._streaming_active is True


def test_render_text_chunk_then_panel_closes_line():
    r, buf = make_renderer()
    r.render_text_chunk("partial")
    r.render_tool_start(ToolCall(id="1", name="Read", arguments={}))
    assert r._streaming_active is False
    out = buf.getvalue()
    # newline must come after "partial" and before the panel
    idx_partial = out.index("partial")
    idx_read = out.index("Read")
    assert "\n" in out[idx_partial:idx_read]


def test_render_assistant_markdown():
    r, buf = make_renderer()
    r.render_assistant_markdown("# Hello\n\nworld")
    out = buf.getvalue()
    assert "Hello" in out
    assert "world" in out


def test_render_assistant_markdown_after_streaming():
    r, buf = make_renderer()
    r.render_text_chunk("streaming")
    r.render_assistant_markdown("done")
    assert r._streaming_active is False


def test_render_tool_start_panel():
    r, buf = make_renderer()
    tc = ToolCall(id="1", name="Read", arguments={"file_path": "/a"})
    r.render_tool_start(tc)
    out = buf.getvalue()
    assert "Read" in out
    assert "/a" in out


def test_render_tool_end_ok():
    r, buf = make_renderer()
    tc = ToolCall(id="1", name="Read", arguments={})
    r.render_tool_end(tc, ToolResult(output="hello"))
    out = buf.getvalue()
    assert "hello" in out
    assert "ok" in out


def test_render_tool_end_error():
    r, buf = make_renderer()
    tc = ToolCall(id="1", name="Bash", arguments={})
    r.render_tool_end(tc, ToolResult(error="boom", is_error=True))
    out = buf.getvalue()
    assert "boom" in out
    assert "error" in out


def test_render_tool_end_truncates_long_output():
    r, buf = make_renderer()
    tc = ToolCall(id="1", name="Read", arguments={})
    long_text = "x" * 5000
    r.render_tool_end(tc, ToolResult(output=long_text))
    out = buf.getvalue()
    assert "truncated" in out
    # the rendered output must not contain all 5000 x's
    assert out.count("x") < 5000


def test_render_tool_denied():
    r, buf = make_renderer()
    tc = ToolCall(id="1", name="Bash", arguments={})
    r.render_tool_denied(tc, "user rejected")
    out = buf.getvalue()
    assert "denied" in out
    assert "user rejected" in out


def test_render_usage_only_if_nonzero():
    r, buf = make_renderer()
    r.render_usage(Usage())
    assert "tokens" not in buf.getvalue()
    r.render_usage(Usage(input_tokens=10, output_tokens=20))
    out = buf.getvalue()
    assert "tokens" in out
    assert "10" in out
    assert "20" in out


def test_render_error():
    r, buf = make_renderer()
    r.render_error("nope")
    assert "nope" in buf.getvalue()


def test_render_error_closes_streaming():
    r, buf = make_renderer()
    r.render_text_chunk("partial")
    r.render_error("bad")
    assert r._streaming_active is False


def test_render_turn_end_closes_streaming():
    r, buf = make_renderer()
    r.render_text_chunk("partial")
    r.render_turn_end()
    assert r._streaming_active is False


def test_render_table():
    r, buf = make_renderer()
    r.render_table("Hi", ["a", "b"], [["1", "2"]])
    out = buf.getvalue()
    assert "Hi" in out
    assert "1" in out
    assert "2" in out
