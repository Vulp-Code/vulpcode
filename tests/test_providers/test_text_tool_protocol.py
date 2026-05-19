"""Tests for the text-based tool-call protocol parser."""
from vulpcode.providers._text_tool_protocol import (
    ParsedResponse,
    parse_response,
    render_protocol_help,
    render_tool_result,
)


# ---------------------------------------------------------------------------
# parse_response — happy paths
# ---------------------------------------------------------------------------


def test_parse_no_tool_block_returns_text_only():
    raw = "This is just plain text with no tool calls."
    result = parse_response(raw)

    assert isinstance(result, ParsedResponse)
    assert result.text == raw
    assert result.tool_calls == []
    assert result.parse_errors == []


def test_parse_single_tool_with_args():
    raw = (
        '<vulp:tool name="WritePy">\n'
        '  <vulp:arg name="file_path">/tmp/hello.py</vulp:arg>\n'
        '</vulp:tool>'
    )
    result = parse_response(raw)

    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert tc.name == "WritePy"
    assert tc.arguments["file_path"] == "/tmp/hello.py"
    assert tc.id.startswith("tt-")
    assert result.parse_errors == []


def test_parse_single_tool_with_content_block():
    raw = (
        '<vulp:tool name="WritePy">\n'
        '  <vulp:arg name="file_path">/tmp/fib.py</vulp:arg>\n'
        '  <vulp:content name="content">\n'
        'def fib(n):\n'
        '    return n\n'
        '  </vulp:content>\n'
        '</vulp:tool>'
    )
    result = parse_response(raw)

    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert tc.name == "WritePy"
    assert "def fib" in tc.arguments["content"]
    assert tc.arguments["file_path"] == "/tmp/fib.py"
    assert result.parse_errors == []


def test_parse_content_block_is_dedented():
    raw = (
        '<vulp:tool name="WritePy">\n'
        '  <vulp:content name="content">\n'
        '    def foo():\n'
        '        pass\n'
        '  </vulp:content>\n'
        '</vulp:tool>'
    )
    result = parse_response(raw)

    content = result.tool_calls[0].arguments["content"]
    # After dedent the common leading whitespace must be removed.
    assert content.startswith("def foo():")
    assert "    pass" in content or "pass" in content
    # No extra indentation on the first line.
    assert not content.startswith(" ")


def test_parse_multiple_tool_blocks():
    raw = (
        "Calling two tools:\n"
        '<vulp:tool name="ReadFile">\n'
        '  <vulp:arg name="path">/tmp/a.txt</vulp:arg>\n'
        '</vulp:tool>\n'
        "Some intermediate prose.\n"
        '<vulp:tool name="WritePy">\n'
        '  <vulp:arg name="file_path">/tmp/b.py</vulp:arg>\n'
        '</vulp:tool>'
    )
    result = parse_response(raw)

    assert len(result.tool_calls) == 2
    names = [tc.name for tc in result.tool_calls]
    assert "ReadFile" in names
    assert "WritePy" in names
    assert result.parse_errors == []


def test_parse_tool_with_no_args_is_valid():
    raw = '<vulp:tool name="NoOp">\n</vulp:tool>'
    result = parse_response(raw)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].arguments == {}
    assert result.parse_errors == []


def test_parse_arg_value_with_equals_sign():
    raw = (
        '<vulp:tool name="Bash">\n'
        '  <vulp:arg name="cmd">python -m foo=bar</vulp:arg>\n'
        '</vulp:tool>'
    )
    result = parse_response(raw)

    assert result.tool_calls[0].arguments["cmd"] == "python -m foo=bar"


# ---------------------------------------------------------------------------
# parse_response — error / edge-case paths
# ---------------------------------------------------------------------------


def test_parse_unclosed_tool_recorded_as_error():
    raw = '<vulp:tool name="WritePy">\n  <vulp:arg name="x">1</vulp:arg>\n'
    result = parse_response(raw)

    assert result.tool_calls == []
    assert len(result.parse_errors) == 1
    assert "unclosed" in result.parse_errors[0].lower()


def test_parse_unclosed_content_drops_whole_block():
    raw = (
        '<vulp:tool name="WritePy">\n'
        '  <vulp:content name="content">\n'
        'some code without closing tag\n'
        '</vulp:tool>'
    )
    result = parse_response(raw)

    # The tool call is dropped entirely because the content block is unclosed.
    assert result.tool_calls == []
    assert len(result.parse_errors) == 1
    assert "unclosed" in result.parse_errors[0].lower()


def test_parse_duplicate_arg_last_wins_and_records_warning():
    raw = (
        '<vulp:tool name="Foo">\n'
        '  <vulp:arg name="x">first</vulp:arg>\n'
        '  <vulp:arg name="x">second</vulp:arg>\n'
        '</vulp:tool>'
    )
    result = parse_response(raw)

    assert result.tool_calls[0].arguments["x"] == "second"
    assert any("duplicate" in e for e in result.parse_errors)


# ---------------------------------------------------------------------------
# parse_response — text extraction
# ---------------------------------------------------------------------------


def test_parse_text_strips_tool_blocks():
    raw = (
        'Thinking out loud.\n'
        '<vulp:tool name="Foo">\n'
        '  <vulp:arg name="x">1</vulp:arg>\n'
        '</vulp:tool>\n'
        'More prose.'
    )
    result = parse_response(raw)

    assert "<vulp:tool" not in result.text
    assert "Thinking out loud." in result.text
    assert "More prose." in result.text


def test_parse_text_preserves_prose_around_blocks():
    prose_before = "Here is my reasoning."
    prose_after = "Done with the calls."
    raw = (
        f"{prose_before}\n"
        '<vulp:tool name="T">\n'
        '  <vulp:arg name="k">v</vulp:arg>\n'
        '</vulp:tool>\n'
        f"{prose_after}"
    )
    result = parse_response(raw)

    assert prose_before in result.text
    assert prose_after in result.text


def test_parse_text_is_raw_when_no_blocks():
    raw = "No tools here.\nJust text."
    result = parse_response(raw)
    assert result.text == raw


# ---------------------------------------------------------------------------
# render_tool_result
# ---------------------------------------------------------------------------


def test_render_tool_result_success():
    rendered = render_tool_result(
        name="WritePy",
        call_id="abc123",
        is_error=False,
        body="Wrote 42 bytes to /tmp/fib.py",
    )

    assert 'name="WritePy"' in rendered
    assert 'id="abc123"' in rendered
    assert 'is_error="false"' in rendered
    assert "Wrote 42 bytes" in rendered
    assert rendered.startswith("<vulp:tool_result")
    assert rendered.endswith("</vulp:tool_result>")


def test_render_tool_result_error_with_multiline_body():
    body = "SyntaxError at line 3:\n  a, b = 0 1\n             ^"
    rendered = render_tool_result(
        name="WritePy",
        call_id="err001",
        is_error=True,
        body=body,
    )

    assert 'is_error="true"' in rendered
    assert "SyntaxError" in rendered
    assert "line 3" in rendered


def test_render_tool_result_is_deterministic():
    first = render_tool_result(name="Foo", call_id="x1", is_error=False, body="ok")
    second = render_tool_result(name="Foo", call_id="x1", is_error=False, body="ok")
    assert first == second


# ---------------------------------------------------------------------------
# render_protocol_help
# ---------------------------------------------------------------------------


def test_render_protocol_help_lists_all_tools():
    schemas = [
        {
            "name": "WritePy",
            "description": "Write a Python file.",
            "parameters": {
                "properties": {
                    "file_path": {"type": "string", "description": "Destination path."},
                    "content": {"type": "string", "description": "Python source."},
                },
                "required": ["file_path", "content"],
            },
        },
        {
            "name": "ReadFile",
            "description": "Read a file.",
            "parameters": {
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        },
    ]
    rendered = render_protocol_help(schemas)

    assert "WritePy" in rendered
    assert "ReadFile" in rendered
    assert "file_path" in rendered
    assert "vulp:tool" in rendered


def test_render_protocol_help_empty_tools():
    rendered = render_protocol_help([])
    assert "vulp:tool" in rendered
    assert "Available tools" in rendered


def test_render_protocol_help_mentions_required_params():
    schemas = [
        {
            "name": "Foo",
            "description": "",
            "input_schema": {
                "properties": {"bar": {"type": "string"}},
                "required": ["bar"],
            },
        }
    ]
    rendered = render_protocol_help(schemas)
    # required params are marked with * in the catalog
    assert "* bar" in rendered
