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

# Hallucinated tool_result detector. Only the harness emits <vulp:tool_result>
# (rendered by render_tool_result/render_cached_tool_result). If the model
# itself emits one, it's making up the result it WISHES the system had
# returned — usually right before ending the turn without a real tool call.
_FAKE_TOOL_RESULT = re.compile(
    r'<vulp:tool_result\b[^>]*>.*?</vulp:tool_result>',
    re.DOTALL,
)
HALLUCINATED_TOOL_RESULT = "HALLUCINATED_TOOL_RESULT"

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

    # Detect hallucinated <vulp:tool_result> blocks. Only the harness produces
    # those; if the model emits one, it's making up a result instead of
    # invoking a tool. Strip them from the visible text and flag the error so
    # the agentic provider can retry with a corrective system message.
    fake_spans = list(_FAKE_TOOL_RESULT.finditer(text))
    if fake_spans:
        errors.append(
            f"{HALLUCINATED_TOOL_RESULT}: model emitted "
            f"{len(fake_spans)} <vulp:tool_result> block(s); only the system "
            "produces tool results — the model must emit <vulp:tool> instead."
        )
        parts = []
        cursor = 0
        for m in fake_spans:
            parts.append(text[cursor:m.start()])
            cursor = m.end()
        parts.append(text[cursor:])
        text = "".join(parts).strip()

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


def render_cached_tool_result(
    *,
    name: str,
    call_id: str,
    is_error: bool,
    preview_body: str,
    full_size: int,
    line_count: int,
) -> str:
    """Render a ``<vulp:tool_result cached="true" ...>`` envelope.

    Used by the agentic provider when a tool result body exceeds the preview
    threshold: full body lives in the ContentStore, the model sees only a
    head+tail preview and is reminded that ``Retrieve(cache_id=...)`` can fetch
    any slice on demand.
    """
    flag = "true" if is_error else "false"
    return (
        f'<vulp:tool_result name="{name}" id="{call_id}" is_error="{flag}" '
        f'cached="true" full_size_chars="{full_size}" total_lines="{line_count}">\n'
        f"{preview_body}\n"
        f"\n[full content cached as cache_id={call_id!r}. "
        f"Fetch any slice with Retrieve(cache_id={call_id!r}, "
        f"start_line=..., end_line=...) or Retrieve(cache_id={call_id!r}, "
        f"pattern=\"...\"). Do NOT re-run the original tool.]\n"
        f"</vulp:tool_result>"
    )


def make_preview(
    body: str,
    *,
    head_lines: int = 40,
    tail_lines: int = 10,
) -> str:
    """Return a compact head+tail preview of ``body`` separated by a marker.

    When the body is short enough to fit both head and tail without overlap,
    the original text is returned unchanged.
    """
    lines = body.splitlines()
    if len(lines) <= head_lines + tail_lines:
        return body
    omitted = len(lines) - head_lines - tail_lines
    head = "\n".join(lines[:head_lines])
    tail = "\n".join(lines[-tail_lines:])
    return (
        f"{head}\n"
        f"\n... [{omitted} middle line(s) omitted — use Retrieve to see them] ...\n\n"
        f"{tail}"
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

# NEVER emit `<vulp:tool_result>` yourself

Only the HARNESS produces `<vulp:tool_result>` blocks — they carry the real
result of a tool you invoked. If YOU emit one, you are fabricating a result
that did not happen: the user sees fake output and the loop ends. This is the
single most damaging failure mode of this protocol.

When a Bash/WebFetch/curl call fails or returns garbage, do NOT pretend it
succeeded. Emit another `<vulp:tool>` block that retries, falls back, or asks
for help. Never close the turn with a hand-written tool_result.

Wrong (catastrophic — you invented the result):
  <vulp:tool_result name="Bash" id="tt-fake" is_error="false">
  This site cannot be reached.
  </vulp:tool_result>

Right (invoke another tool to actually handle the failure):
  <vulp:tool name="Bash">
    <vulp:arg name="command">curl -sIL --max-time 10 "https://fallback.example/x.pdf"</vulp:arg>
  </vulp:tool>

# No phantom commits — MOST IMPORTANT RULE

If an action is needed, emit the `<vulp:tool>` block in the SAME response. NEVER
end your turn with a promise like "vou ler", "vou analisar", "Agora vou buscar",
"let me check", "I'll read", "vamos abrir" without an accompanying tool block.
A promise with no tool block produces NOTHING on the user's side — the user sees
only the sentence and nothing happens.

This rule applies to EVERY turn, including turns that follow a tool result.
After a `<vulp:tool_result>` arrives, if more work is needed, your VERY NEXT
emission must be another tool block. You may write one short prose line of
acknowledgement, but it must be followed by a tool block in the same response.

Wrong (DO NOT do this — your turn ends, nothing executes):
  vou ler o arquivo para análise.

Wrong (same problem — promise after a tool result):
  Identifiquei os arquivos. Agora, vou buscar a coluna nr_x em cada um.

Right (emit the call directly, with or without a short prose line):
Found the files. Searching now:
<vulp:tool name="Grep">
  <vulp:arg name="pattern">nr_x</vulp:arg>
  <vulp:arg name="path">/abs/dir</vulp:arg>
  <vulp:arg name="output_mode">files_with_matches</vulp:arg>
</vulp:tool>

## Follow-through after listing tools

When the user's goal involves searching CONTENT (a column name, a function, a
keyword, etc.) and you just listed files via `Glob` or `Tree`, your NEXT
emission is OBLIGATORILY a `<vulp:tool name="Grep">` block. Not a sentence
about what you'll do — the actual block.

Same pattern for other goals:
  - "find the entry point" → after Tree/Glob, next is `Grep` for `main`/`if __name__`.
  - "understand this file" → after Glob locates it, next is `Read`.
  - "what's in this column" → after Glob lists files, next is `Grep` for the header.

If you don't know the absolute path, call `Glob` first to discover it. Either
way: do not stop at the promise.

Tool results return as:

<vulp:tool_result name="X" id="..." is_error="true|false">
... body / error message ...
</vulp:tool_result>

# Exploring a project — CRITICAL when context is limited

This endpoint has a tight 128k-token input window. NEVER try to dump a whole
project into context. Explore in layers, from cheap to expensive:

1. **Structure first.** Run `Tree` on the project root (or use `Glob '**/*'`
   with a filter) BEFORE reading any file. You get the layout in a few hundred
   lines; you'd otherwise spend thousands of tokens listing files via Read.
   `Tree` already skips noise dirs (node_modules, __pycache__, .venv, .git,
   dist, build, target, ...) and honors .gitignore.

2. **Anchors second.** Read the small "what is this" files:
   `README*`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`,
   `Makefile`, `docker-compose.yml`. These reveal language, framework,
   entry points, and dependencies in a few KB.

3. **Symbols via Grep.** Before reading source files, use `Grep` to extract
   signatures and find candidates. Examples:
     - `Grep '^class ' --output_mode files_with_matches`
     - `Grep '^def main\b' src/`
     - `Grep 'from foo import' --output_mode count`
   `Grep` is also ignore-aware by default. Much cheaper than `Read`.

4. **Read selectively.** Only after the previous steps, `Read` the specific
   files you've decided are relevant. For files > 500 lines, pass `offset` and
   `limit` to grab the regions you actually need.

Anti-patterns to AVOID:
- `Read`-ing every file you find from `Glob`.
- `Bash('ls -R')` or `Bash('find .')` — use `Tree`/`Glob` instead (filtered).
- Passing `include_ignored=true` to `Glob`/`Grep`/`Tree` unless the user
  explicitly asks about hidden/ignored files.

# Cached tool results — when you see `cached="true"`

Large tool results (long file reads, big grep dumps, heavy bash output) are
NOT sent to you in full. Instead, you'll see:

<vulp:tool_result name="Read" id="tt-abc" is_error="false" cached="true"
                  full_size_chars="48312" total_lines="850">
[first 40 lines of output]
... [middle lines omitted — use Retrieve to see them] ...
[last 10 lines of output]
[full content cached as cache_id='tt-abc'. Fetch any slice with
 Retrieve(cache_id='tt-abc', start_line=..., end_line=...) or
 Retrieve(cache_id='tt-abc', pattern="..."). Do NOT re-run the original tool.]
</vulp:tool_result>

When you need a specific section of that body, call the `Retrieve` tool with
the `cache_id` shown — it's an in-memory lookup, no I/O, much cheaper than
re-running Read/Grep/Bash. Three modes:

  - By line range:    Retrieve(cache_id="tt-abc", start_line=200, end_line=260)
  - By regex:         Retrieve(cache_id="tt-abc", pattern="^class ", context_lines=3)
  - First 400 lines:  Retrieve(cache_id="tt-abc")

NEVER re-issue the original tool (Read/Grep/Bash) just to see more of a cached
result — the file/state may have changed, and you'd waste an LLM round-trip.

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
