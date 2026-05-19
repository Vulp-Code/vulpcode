from vulpcode.providers._text_tool_protocol import render_protocol_help


def test_protocol_help_lists_all_provided_tools():
    tools = [
        {
            "name": "WritePy",
            "description": "Write a .py",
            "input_schema": {
                "properties": {
                    "file_path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["file_path", "content"],
            },
        },
    ]
    out = render_protocol_help(tools)
    assert "WritePy" in out
    assert "file_path" in out
    assert '<vulp:tool name="' in out


def test_protocol_help_marks_required_args():
    tools = [
        {
            "name": "X",
            "description": "y",
            "input_schema": {
                "properties": {
                    "a": {"type": "string"},
                    "b": {"type": "string"},
                },
                "required": ["a"],
            },
        }
    ]
    out = render_protocol_help(tools)
    assert "* a:" in out  # required
    assert "  b:" in out  # optional


def test_protocol_help_includes_repair_loop():
    out = render_protocol_help([])
    assert "Repair loop" in out
    assert "CRITICAL" in out
    assert "is_error" in out


def test_protocol_help_includes_few_shot_example():
    out = render_protocol_help([])
    assert "# Example" in out
    assert "WritePy" in out
    assert "Done." in out


def test_protocol_help_truncates_long_descriptions():
    long_desc = "x" * 200
    tools = [
        {
            "name": "T",
            "description": "short",
            "input_schema": {
                "properties": {"p": {"type": "string", "description": long_desc}},
                "required": [],
            },
        }
    ]
    out = render_protocol_help(tools)
    # Truncated description should not appear in full
    assert long_desc not in out
    # But the arg should still be listed
    assert "p:" in out


def test_protocol_help_empty_tools():
    out = render_protocol_help([])
    assert "# Tool calling protocol" in out
    assert "# Available tools" in out


def test_protocol_help_warns_against_phantom_commits():
    """The prompt must instruct the model NOT to promise without emitting a tool."""
    out = render_protocol_help([])
    assert "No phantom commits" in out
    # Mentions both PT and EN commitment phrases the heuristic looks for.
    assert "vou" in out.lower()
    assert "let me" in out.lower()
    # Shows the wrong-pattern example so the model can pattern-match.
    assert "vou ler" in out.lower()


def test_protocol_help_uses_override_for_write_ipynb():
    tools = [
        {
            "name": "WriteIpynb",
            "description": "This is a very long description that would normally be shown",
            "input_schema": {"properties": {}, "required": []},
        }
    ]
    out = render_protocol_help(tools)
    assert "WriteIpynb" in out
    # Override description should be used instead of original
    assert "Jupyter notebook" in out
