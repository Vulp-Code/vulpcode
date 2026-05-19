"""Text-based tool-call protocol for the InternalLLMAgenticProvider.

The protocol embeds tool calls and results in plain text using a lightweight
XML-ish syntax with the ``vulp:`` namespace.  A regex + linear scanner is used
instead of a real XML parser so that:

- Literal ``<`` characters inside ``<vulp:content>`` blocks (common in code) do
  not need escaping.
- The parser is tolerant of free text surrounding the protocol blocks.
- No third-party or stdlib XML dependency is introduced.

Known limitation: a ``</vulp:content>`` literal *inside* a content block will
terminate the block prematurely.  The system prompt advises the model to write
``</vulp:content_literal>`` as an escape; the agent reverts it before writing.
"""
from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from vulpcode.providers.base import ToolCall


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_TOOL_OPEN = re.compile(
    r'<vulp:tool\s+name="([A-Za-z_][A-Za-z0-9_]*)"\s*>',
    re.MULTILINE,
)
_TOOL_CLOSE = "</vulp:tool>"

_ARG_RE = re.compile(
    r'<vulp:arg\s+name="([^"]+)"\s*>(.*?)</vulp:arg>',
    re.DOTALL,
)
_CONTENT_OPEN_RE = re.compile(
    r'<vulp:content\s+name="([^"]+)"\s*>',
    re.DOTALL,
)
_CONTENT_CLOSE = "</vulp:content>"


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class ParsedResponse:
    """Result of parsing a plain-text response from the endpoint."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser internals
# ---------------------------------------------------------------------------


def _parse_inner(inner: str, tool_name: str, errors: list[str]) -> dict[str, Any] | None:
    """Parse the body between ``<vulp:tool>`` and ``</vulp:tool>``.

    Returns a dict of arguments, or ``None`` if a fatal inner error is found
    (e.g. unclosed ``<vulp:content>``).
    """
    arguments: dict[str, Any] = {}

    # --- scalar args ---
    for m in _ARG_RE.finditer(inner):
        key = m.group(1)
        value = m.group(2).strip()
        if key in arguments:
            errors.append(
                f"duplicate argument '{key}' in tool '{tool_name}'; last value wins"
            )
        arguments[key] = value

    # --- content blocks ---
    search_start = 0
    while True:
        open_m = _CONTENT_OPEN_RE.search(inner, search_start)
        if open_m is None:
            break

        key = open_m.group(1)
        body_start = open_m.end()
        close_idx = inner.find(_CONTENT_CLOSE, body_start)

        if close_idx == -1:
            errors.append(
                f"unclosed <vulp:content name=\"{key}\"> in tool '{tool_name}'; "
                "dropping entire tool call"
            )
            return None

        raw_body = inner[body_start:close_idx]
        # Strip the first and last blank lines then dedent.
        body = textwrap.dedent(raw_body.strip("\n"))

        if key in arguments:
            errors.append(
                f"duplicate argument '{key}' in tool '{tool_name}'; last value wins"
            )
        arguments[key] = body

        search_start = close_idx + len(_CONTENT_CLOSE)

    return arguments


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_response(raw: str) -> ParsedResponse:
    """Parse a raw text response and extract embedded tool calls.

    Text that falls outside ``<vulp:tool>…</vulp:tool>`` blocks is returned
    as ``ParsedResponse.text``.  Malformed blocks are skipped and recorded in
    ``ParsedResponse.parse_errors`` — they never raise.
    """
    errors: list[str] = []
    tool_calls: list[ToolCall] = []
    # Track which character ranges belong to tool blocks so we can strip them.
    tool_spans: list[tuple[int, int]] = []

    search_start = 0
    while True:
        open_m = _TOOL_OPEN.search(raw, search_start)
        if open_m is None:
            break

        tool_name = open_m.group(1)
        inner_start = open_m.end()
        close_idx = raw.find(_TOOL_CLOSE, inner_start)

        if close_idx == -1:
            errors.append(
                f"unclosed <vulp:tool name=\"{tool_name}\">; skipping"
            )
            search_start = inner_start
            continue

        block_end = close_idx + len(_TOOL_CLOSE)
        tool_spans.append((open_m.start(), block_end))

        inner = raw[inner_start:close_idx]
        arguments = _parse_inner(inner, tool_name, errors)

        if arguments is not None:
            call_id = f"tt-{uuid4().hex[:8]}"
            tool_calls.append(ToolCall(id=call_id, name=tool_name, arguments=arguments))

        search_start = block_end

    # Build the text by removing all tool block spans.
    if tool_spans:
        parts: list[str] = []
        cursor = 0
        for start, end in tool_spans:
            parts.append(raw[cursor:start])
            cursor = end
        parts.append(raw[cursor:])
        text = "".join(parts).strip()
    else:
        text = raw

    return ParsedResponse(text=text, tool_calls=tool_calls, parse_errors=errors)


def render_tool_result(
    *,
    name: str,
    call_id: str,
    is_error: bool,
    body: str,
) -> str:
    """Render a ``<vulp:tool_result>`` envelope for injection as a user message."""
    flag = "true" if is_error else "false"
    return (
        f'<vulp:tool_result name="{name}" id="{call_id}" is_error="{flag}">\n'
        f"{body}\n"
        f"</vulp:tool_result>"
    )


_PROMPT_TEMPLATE = """\
# Tool calling protocol

You are running against an endpoint that does NOT support native tool calling.
To invoke a tool, emit one or more blocks in this exact format inside your response:

<vulp:tool name="ToolName">
  <vulp:arg name="key">scalar value</vulp:arg>
  <vulp:content name="content">
multi-line
content goes here
verbatim
  </vulp:content>
</vulp:tool>

Rules:
- Tag names are case-sensitive: lowercase `vulp:tool`, `vulp:arg`, `vulp:content`.
- Use `<vulp:arg>` for short scalar values (paths, numbers, single words).
- Use `<vulp:content>` for multi-line or code-containing values.
- The content of `<vulp:content>` is taken literally — do NOT escape special chars.
- Indentation of the `<vulp:content>` body is preserved relative to the block (common
  leading whitespace is stripped, so you can indent the XML naturally).
- Emit ZERO prose between tool blocks. Prose goes BEFORE the first block or AFTER the
  last one. Brief is best.

# No phantom commits — CRITICAL

If an action is needed, emit the `<vulp:tool>` block in the SAME response. NEVER
end your turn with a promise like "vou ler", "vou analisar", "let me check",
"I'll read", "vamos abrir" without an accompanying tool block. A promise with no
tool block produces NOTHING on the user's side — the user sees only the sentence
and nothing happens.

Wrong (DO NOT do this — your turn ends, nothing executes):
  vou ler o arquivo para análise.

Right (DO this — emit the call directly, with or without prose):
<vulp:tool name="Read">
  <vulp:arg name="file_path">/abs/path/exemplo.txt</vulp:arg>
</vulp:tool>

If you don't know the absolute path, call `Glob` or `Bash` (e.g. `ls`) first to
discover it. Either way: do not stop at the promise.

Tool results return as:

<vulp:tool_result name="X" id="..." is_error="true|false">
... body / error message ...
</vulp:tool_result>

# Repair loop — CRITICAL

If a `<vulp:tool_result is_error="true">` arrives, you MUST:
  1. Read the error message carefully — it includes line, column, and a code snippet.
  2. Identify the exact cause (often a typo, missing colon, unbalanced brace, etc.).
  3. Re-emit the SAME tool with corrected content. Do NOT switch tools or apologise.
  4. Repeat. Most syntax errors are fixed in 1–2 retries.

Do NOT respond with prose like "Sorry, let me try again". Just emit the corrected tool
call. The user only cares about the final working file.

If after 3 retries the same error persists, then explain to the user what is blocking
you and ask for guidance. Otherwise, keep iterating.

# Example

User: create a file /tmp/hello.py that prints "hello"

You (correct response — NO prose):
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">/tmp/hello.py</vulp:arg>
  <vulp:content name="content">
print("hello")
  </vulp:content>
</vulp:tool>

(tool result arrives)
<vulp:tool_result name="WritePy" id="..." is_error="false">
Wrote 15 bytes to /tmp/hello.py
</vulp:tool_result>

You (final ack — short):
Done.

# Available tools

{TOOL_CATALOG}"""

# Short description overrides for tools whose auto-generated descriptions would be
# too long for the system prompt catalog (e.g. tools with deeply nested schemas).
_TOOL_HELP_OVERRIDES: dict[str, str] = {
    "WriteIpynb": (
        "Write a Jupyter notebook (.ipynb). "
        "Args: file_path (string), cells (JSON array of {cell_type, source, outputs?})."
    ),
    "WriteDocx": (
        "Write a Word document (.docx). "
        "Args: file_path (string), content (markdown-formatted text)."
    ),
    "WritePdf": (
        "Write a PDF document. "
        "Args: file_path (string), content (plain text or markdown)."
    ),
}

_MAX_DESC_LEN = 80


def _truncate(s: str, max_len: int = _MAX_DESC_LEN) -> str:
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def render_protocol_help(tools: list[dict]) -> str:
    """Render the tool catalog and protocol instructions for system-prompt injection.

    Args:
        tools: List of tool schemas as returned by ``Tool.to_schema()``.  Each
            schema must have ``name`` and optionally ``description`` and
            ``input_schema``.

    Returns:
        A complete system-prompt string that teaches the model to use the
        text-based tool-calling protocol.
    """
    catalog: list[str] = []
    for t in tools:
        name = t.get("name", "<unknown>")
        description = _TOOL_HELP_OVERRIDES.get(name) or t.get("description", "")
        schema = t.get("input_schema", {})
        props = schema.get("properties", {})
        req = set(schema.get("required", []))
        args_lines: list[str] = []
        for k, v in props.items():
            kind = v.get("type", "any")
            marker = "*" if k in req else " "
            raw_desc = v.get("description", "")
            desc = _truncate(raw_desc) if raw_desc else ""
            args_lines.append(f"  {marker} {k}: {kind}{(' — ' + desc) if desc else ''}")
        args_block = "\nArgs:\n" + "\n".join(args_lines) if args_lines else ""
        catalog.append(f"## {name}\n{description}{args_block}")

    return _PROMPT_TEMPLATE.replace("{TOOL_CATALOG}", "\n\n".join(catalog))
