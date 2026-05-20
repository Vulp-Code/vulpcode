"""Provider for an internal corporate /chatCompletion endpoint with text-based tool calling.

Wraps the same transport as InternalLLMProvider but adds an XML-ish text protocol
on top so tool calls work even though the endpoint has no native tool_use field.

Two endpoint constraints are enforced here so they cannot break a turn:

- **60 s server-side timeout.** Default client timeout is 55 s; a timeout retries
  once with halved ``max_tokens`` (output that doesn't fit in 60 s is the most
  common cause). After ``max_retries`` we surface a clear ProviderError.
- **128 k input token limit.** Before each POST the provider estimates input
  tokens (char/4 heuristic) and, if over ``max_input_tokens``, trims older
  ``<vulp:tool_result>`` bodies and drops oldest middle messages while
  preserving the system prompt, the first user message, and the most recent
  turns. A short "[context optimized: …]" notice is streamed back so the caller
  knows it happened.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from typing import Any, AsyncIterator

import httpx

from vulpcode.providers._content_store import ContentStore, get_default_store
from vulpcode.providers._internal_llm_agentic_config import (
    ConfigCreated,
    ConfigIncomplete,
    load_or_init as _load_user_config,
    render_created_message,
    render_incomplete_message,
)
from vulpcode.providers._text_tool_protocol import (
    HALLUCINATED_TOOL_RESULT,
    make_preview,
    parse_response,
    render_cached_tool_result,
    render_protocol_help,
    render_tool_result,
)
from vulpcode.providers.base import (
    Message,
    Provider,
    ProviderError,
    StreamChunk,
    Usage,
)


def _resolve_ref(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return schema
    node: Any = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            return schema
        node = node[part]
    return node if isinstance(node, dict) else schema


def _expected_types(prop_schema: dict[str, Any], root: dict[str, Any]) -> set[str]:
    seen: set[int] = set()
    out: set[str] = set()

    def walk(s: Any) -> None:
        if not isinstance(s, dict) or id(s) in seen:
            return
        seen.add(id(s))
        s = _resolve_ref(s, root)
        t = s.get("type")
        if isinstance(t, str):
            out.add(t)
        elif isinstance(t, list):
            out.update(x for x in t if isinstance(x, str))
        for key in ("anyOf", "oneOf", "allOf"):
            for sub in s.get(key, []) or []:
                walk(sub)

    walk(prop_schema)
    return out


def _coerce_text_args(
    arguments: dict[str, Any], input_schema: dict[str, Any]
) -> dict[str, Any]:
    """JSON-decode string args when the schema expects array/object.

    The text tool-calling protocol can only deliver strings across the wire,
    so a tool whose Input declares ``list[...]`` or ``dict[...]`` will receive
    a JSON-encoded blob instead of the parsed value. Pydantic then rejects
    the string. This helper unblocks it without changing per-tool schemas.
    Silent no-op when the string is not valid JSON.
    """
    props = input_schema.get("properties") if isinstance(input_schema, dict) else None
    if not isinstance(props, dict) or not isinstance(arguments, dict):
        return arguments
    out = dict(arguments)
    for key, value in arguments.items():
        if not isinstance(value, str):
            continue
        prop_schema = props.get(key)
        if not isinstance(prop_schema, dict):
            continue
        types = _expected_types(prop_schema, input_schema)
        if not (types & {"array", "object"}):
            continue
        stripped = value.strip()
        if not stripped or stripped[0] not in "[{":
            continue
        try:
            out[key] = json.loads(stripped)
        except (ValueError, TypeError):
            pass
    return out


class InternalLLMAgenticProvider(Provider):
    """Internal /chatCompletion endpoint + text-based tool calling shim."""

    name = "internal-llm-agentic"

    DEFAULT_TIMEOUT = 55.0
    DEFAULT_MAX_INPUT_TOKENS = 115_000
    DEFAULT_PREVIEW_THRESHOLD = 4_000
    DEFAULT_PREVIEW_HEAD_LINES = 40
    DEFAULT_PREVIEW_TAIL_LINES = 10
    DEFAULT_AUTO_COMPACT_AT = 0.85
    _CHARS_PER_TOKEN = 4
    _PRESERVE_TAIL = 2
    _AUTO_COMPACT_TAIL = 4
    _AUTO_COMPACT_MIN_MIDDLE = 4
    _AUTO_COMPACT_MAX_TOKENS = 800
    _AUTO_COMPACT_SYSTEM = (
        "You are a concise summarizer of a coding-agent conversation. "
        "Produce ONE paragraph (max ~150 words) that preserves: concrete file "
        "paths touched, decisions made, open TODOs, key findings, and any "
        "errors encountered. Skip pleasantries. Past tense, third person."
    )
    _PER_RESULT_CHAR_BUDGET = 2_000
    _MIN_MAX_TOKENS = 500
    _TRUNC_NOTE = "\n...[content truncated to fit context window]..."

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        user_uuid: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        preview_threshold: int = DEFAULT_PREVIEW_THRESHOLD,
        preview_head_lines: int = DEFAULT_PREVIEW_HEAD_LINES,
        preview_tail_lines: int = DEFAULT_PREVIEW_TAIL_LINES,
        content_store: ContentStore | None = None,
        auto_compact: bool = False,
        auto_compact_at: float = DEFAULT_AUTO_COMPACT_AT,
        **extra: Any,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url, timeout=timeout, **extra)
        self.endpoint = base_url
        self.user_uuid = user_uuid
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_input_tokens = max_input_tokens
        self.preview_threshold = preview_threshold
        self.preview_head_lines = preview_head_lines
        self.preview_tail_lines = preview_tail_lines
        self.content_store = (
            content_store if content_store is not None else get_default_store()
        )
        self.auto_compact = auto_compact
        self.auto_compact_at = auto_compact_at
        self.timeout = timeout
        self._default_max_tokens: int | None = max_output_tokens
        self._default_temperature: float | None = temperature
        self._default_top_p: float | None = top_p

        if (not self.endpoint or not self.user_uuid) and "pytest" not in sys.modules:
            self._apply_user_config_file()

        self._client = httpx.AsyncClient(timeout=self.timeout)

    def _apply_user_config_file(self) -> None:
        """Load ``~/.vulpcode/internal-llm-agentic.json`` and fill missing fields.

        Called only when ``endpoint`` or ``user_uuid`` were not supplied via
        kwargs/env/TOML. If the JSON file is missing or incomplete, print a
        Portuguese message telling the user what to edit and exit with code 2
        — this matches the explicit "configure and restart" UX requirement.
        """
        try:
            data = _load_user_config()
        except ConfigCreated as exc:
            print(render_created_message(exc.path), file=sys.stderr)
            raise SystemExit(2) from exc
        except ConfigIncomplete as exc:
            print(
                render_incomplete_message(exc.path, exc.missing),
                file=sys.stderr,
            )
            raise SystemExit(2) from exc

        if not self.endpoint:
            self.endpoint = data.get("endpoint")
        if not self.user_uuid:
            self.user_uuid = data.get("user_uuid")

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return False

    async def aclose(self) -> None:
        await self._client.aclose()

    def _build_system(
        self, system: str | None, tools: list[dict[str, Any]]
    ) -> str:
        """Augment the user-supplied system prompt with the protocol help."""
        protocol_block = render_protocol_help(tools)
        if system:
            return f"{system}\n\n{protocol_block}"
        return protocol_block

    def _flatten(self, messages: list[Message]) -> list[dict[str, str]]:
        """Convert canonical messages for the endpoint.

        - role="tool" -> user message containing <vulp:tool_result>...</vulp:tool_result>.
          If the body exceeds ``preview_threshold``, the full body is stashed in
          ``self.content_store`` and only a head+tail preview is emitted; the model
          can call ``Retrieve(cache_id=...)`` to fetch slices.
        - role="assistant" with tool_calls -> keep only the text part (the XML was the text)
        """
        out: list[dict[str, str]] = []
        for m in messages:
            if m.role == "tool":
                body = m.content if isinstance(m.content, str) else ""
                is_err = body.startswith("Error:")
                clean_body = body[len("Error:"):].strip() if is_err else body
                call_id = m.tool_call_id or "unknown"
                tool_name = m.name or "unknown"

                if len(clean_body) > self.preview_threshold:
                    stored = self.content_store.put(
                        cache_id=call_id,
                        tool_name=tool_name,
                        full_body=clean_body,
                        is_error=is_err,
                    )
                    preview = make_preview(
                        clean_body,
                        head_lines=self.preview_head_lines,
                        tail_lines=self.preview_tail_lines,
                    )
                    envelope = render_cached_tool_result(
                        name=tool_name,
                        call_id=call_id,
                        is_error=is_err,
                        preview_body=preview,
                        full_size=stored.size_chars,
                        line_count=stored.line_count,
                    )
                else:
                    envelope = render_tool_result(
                        name=tool_name,
                        call_id=call_id,
                        is_error=is_err,
                        body=clean_body,
                    )
                out.append({"role": "user", "content": envelope})
            elif m.role == "assistant":
                text = m.content if isinstance(m.content, str) else ""
                if text:
                    out.append({"role": "assistant", "content": text})
            else:
                content = m.content if isinstance(m.content, str) else ""
                out.append({"role": m.role, "content": content})
        return out

    @classmethod
    def _estimate_tokens(cls, text: str) -> int:
        """Rough char/4 estimator. Conservative for code-heavy English/Portuguese."""
        if not text:
            return 0
        return max(1, len(text) // cls._CHARS_PER_TOKEN)

    @classmethod
    def _messages_tokens(cls, msgs: list[dict[str, str]]) -> int:
        return sum(cls._estimate_tokens(m.get("content", "")) for m in msgs)

    @classmethod
    def _truncate_tool_result(cls, content: str, max_chars: int) -> str:
        """Truncate the body inside a <vulp:tool_result> envelope, keeping the tags."""
        if len(content) <= max_chars:
            return content
        open_match = re.search(r"(<vulp:tool_result[^>]*>)\n?", content)
        close_tag = "</vulp:tool_result>"
        close_idx = content.rfind(close_tag)
        if not open_match or close_idx == -1:
            return content[: max(0, max_chars - len(cls._TRUNC_NOTE))] + cls._TRUNC_NOTE
        head_end = open_match.end()
        body_budget = max(
            200,
            max_chars - head_end - len(close_tag) - len(cls._TRUNC_NOTE),
        )
        return (
            content[:head_end]
            + content[head_end : head_end + body_budget]
            + cls._TRUNC_NOTE
            + "\n"
            + close_tag
        )

    def _fit_budget(
        self, api_messages: list[dict[str, str]]
    ) -> tuple[list[dict[str, str]], str | None]:
        """Trim api_messages so estimated tokens stay under ``max_input_tokens``.

        Strategy (each step short-circuits when under budget):
          1. Truncate every oversize ``<vulp:tool_result>`` body **except the
             most recent one** — file/grep blobs from prior turns are the
             cheapest thing to lose.
          2. Drop oldest middle messages outright (preserving system, first
             user message, and the last ``_PRESERVE_TAIL`` messages); insert
             one placeholder so the model knows context was dropped.
          3. Last resort: truncate the most recent oversize tool_result too.

        Returns ``(msgs, note)`` where ``note`` is a short human-readable
        summary of what was trimmed, or ``None`` if nothing changed.
        """
        limit = self.max_input_tokens
        total = self._messages_tokens(api_messages)
        if total <= limit:
            return api_messages, None

        msgs = list(api_messages)
        notes: list[str] = []

        n = len(msgs)
        head = min(2, n)  # system + first user message
        tail_start = max(head, n - self._PRESERVE_TAIL)

        # Step 1: truncate every oversize tool_result that's NOT in the preserved tail.
        truncated_count = 0
        for i in range(0, tail_start):
            content = msgs[i].get("content", "")
            if (
                "<vulp:tool_result" in content
                and len(content) > self._PER_RESULT_CHAR_BUDGET
            ):
                msgs[i] = {
                    **msgs[i],
                    "content": self._truncate_tool_result(
                        content, self._PER_RESULT_CHAR_BUDGET
                    ),
                }
                truncated_count += 1
        if truncated_count:
            notes.append(f"truncated {truncated_count} old tool result(s)")

        total = self._messages_tokens(msgs)
        if total <= limit:
            return msgs, "; ".join(notes) if notes else None

        # Step 2: drop oldest middle messages.
        middle = list(range(head, tail_start))
        dropped = 0
        while total > limit and middle:
            drop_idx = middle.pop(0)
            total -= self._estimate_tokens(msgs[drop_idx].get("content", ""))
            dropped += 1

        if dropped:
            rebuilt: list[dict[str, str]] = (
                msgs[:head]
                + [msgs[i] for i in middle]
                + msgs[tail_start:]
            )
            placeholder = {
                "role": "user",
                "content": (
                    f"[{dropped} earlier message(s) omitted to fit the "
                    f"{limit}-token context window]"
                ),
            }
            rebuilt.insert(head, placeholder)
            notes.append(f"dropped {dropped} old message(s)")
            msgs = rebuilt

        total = self._messages_tokens(msgs)
        if total <= limit:
            return msgs, "; ".join(notes) if notes else None

        # Step 3: as a last resort, truncate the most recent oversize tool_result.
        for i in range(len(msgs) - 1, -1, -1):
            content = msgs[i].get("content", "")
            if (
                "<vulp:tool_result" in content
                and len(content) > self._PER_RESULT_CHAR_BUDGET
            ):
                msgs[i] = {
                    **msgs[i],
                    "content": self._truncate_tool_result(
                        content, self._PER_RESULT_CHAR_BUDGET
                    ),
                }
                notes.append("truncated most recent tool result")
                break

        return msgs, "; ".join(notes) if notes else None

    def _needs_auto_compact(self, api_messages: list[dict[str, str]]) -> bool:
        """True when conversation crossed the auto-compact threshold and is long enough."""
        n = len(api_messages)
        # Need: system + first user + enough middle + tail to be worth summarizing.
        if n < 2 + self._AUTO_COMPACT_MIN_MIDDLE + self._AUTO_COMPACT_TAIL:
            return False
        total = self._messages_tokens(api_messages)
        threshold = int(self.max_input_tokens * self.auto_compact_at)
        return total > threshold

    async def _auto_compact(
        self, api_messages: list[dict[str, str]]
    ) -> tuple[list[dict[str, str]], str | None]:
        """Summarize the middle of ``api_messages`` via one extra endpoint POST.

        Returns ``(new_messages, note)``. On any failure (timeout, HTTP error,
        empty response) returns ``(api_messages, None)`` so the caller can fall
        back to :meth:`_fit_budget`. Never raises.
        """
        n = len(api_messages)
        head = min(2, n)
        tail_start = max(head, n - self._AUTO_COMPACT_TAIL)
        middle = api_messages[head:tail_start]
        if len(middle) < self._AUTO_COMPACT_MIN_MIDDLE:
            return api_messages, None

        transcript_parts: list[str] = []
        for m in middle:
            role = m.get("role", "user")
            content = m.get("content", "")
            # Truncate huge tool_results before summarizing — summarizer must fit
            # in the same 128k window itself.
            if (
                "<vulp:tool_result" in content
                and len(content) > self._PER_RESULT_CHAR_BUDGET
            ):
                content = self._truncate_tool_result(
                    content, self._PER_RESULT_CHAR_BUDGET
                )
            transcript_parts.append(f"[{role}]\n{content}")
        transcript = "\n\n".join(transcript_parts)

        summarize_payload = {
            "data": {
                "solicitacao": {
                    "messages": [
                        {"role": "system", "content": self._AUTO_COMPACT_SYSTEM},
                        {
                            "role": "user",
                            "content": f"Transcript to summarize:\n\n{transcript}",
                        },
                    ]
                },
                "config": {
                    "temperature": 0.3,
                    "max_tokens": self._AUTO_COMPACT_MAX_TOKENS,
                    "top_p": 0.95,
                },
            },
        }
        headers = {
            "user-uuid": self.user_uuid,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

        try:
            resp = await self._client.post(
                self.endpoint, headers=headers, json=summarize_payload
            )
        except httpx.HTTPError:
            return api_messages, None
        if resp.status_code >= 400:
            return api_messages, None
        try:
            data = resp.json().get("data")
        except ValueError:
            return api_messages, None
        if not data:
            return api_messages, None
        summary = str(data).strip()
        if not summary:
            return api_messages, None

        placeholder = {
            "role": "user",
            "content": (
                f"[Previous conversation summary — {len(middle)} message(s) "
                f"replaced to fit context window]\n\n{summary}"
            ),
        }
        new_msgs = api_messages[:head] + [placeholder] + api_messages[tail_start:]
        return new_msgs, f"auto-compacted {len(middle)} message(s) into a summary"

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        if not self.endpoint:
            raise ProviderError(
                "internal-llm-agentic requires base_url. Set INTERNAL_LLM_ENDPOINT "
                "or providers.internal-llm-agentic.base_url in config.toml."
            )
        if not self.user_uuid:
            raise ProviderError(
                "internal-llm-agentic requires user_uuid. Set INTERNAL_LLM_USER_UUID "
                "or providers.internal-llm-agentic.user_uuid in config.toml."
            )

        api_messages = self._flatten(messages)
        full_system = self._build_system(system, tools)
        api_messages.insert(0, {"role": "system", "content": full_system})

        compact_note: str | None = None
        if self.auto_compact and self._needs_auto_compact(api_messages):
            api_messages, compact_note = await self._auto_compact(api_messages)

        api_messages, budget_note = self._fit_budget(api_messages)
        if compact_note and budget_note:
            budget_note = f"{compact_note}; {budget_note}"
        elif compact_note:
            budget_note = compact_note

        max_tokens = kwargs.pop("max_tokens", self._default_max_tokens or 3000)
        temperature = kwargs.pop("temperature", self._default_temperature or 0.3)
        top_p = kwargs.pop("top_p", self._default_top_p or 0.95)

        payload = {
            "data": {
                "solicitacao": {"messages": api_messages},
                "config": {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                },
            },
        }
        headers = {
            "user-uuid": self.user_uuid,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

        last_error: str | None = None
        raw_text: str | None = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._client.post(
                    self.endpoint, headers=headers, json=payload
                )
            except httpx.TimeoutException as exc:
                last_error = f"timeout after {self.timeout}s: {exc}"
                if attempt < self.max_retries - 1:
                    current = payload["data"]["config"]["max_tokens"]
                    payload["data"]["config"]["max_tokens"] = max(
                        self._MIN_MAX_TOKENS, current // 2
                    )
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise ProviderError(
                    f"endpoint exceeded {self.timeout}s timeout after "
                    f"{self.max_retries} attempts. Try a shorter prompt or "
                    f"a smaller max_tokens."
                ) from exc
            except httpx.HTTPError as exc:
                last_error = f"network error: {exc}"
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise ProviderError(last_error) from exc

            if resp.status_code >= 400:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if attempt < self.max_retries - 1 and resp.status_code >= 500:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise ProviderError(last_error)

            try:
                payload_response = resp.json()
            except ValueError as exc:
                raise ProviderError(
                    f"endpoint returned non-JSON: {exc}"
                ) from exc

            data = (
                payload_response.get("data")
                if isinstance(payload_response, dict)
                else None
            )
            if data is None:
                last_error = f"endpoint returned data=null (attempt {attempt+1}/{self.max_retries})"
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise ProviderError(last_error)

            raw_text = str(data)
            break

        if raw_text is None:
            raise ProviderError(last_error or "internal-llm-agentic failed after retries")

        if budget_note:
            yield StreamChunk(
                type="text",
                delta=f"[context optimized: {budget_note}]\n\n",
            )

        parsed = parse_response(raw_text)

        # Auto-recovery: if the model fabricated a <vulp:tool_result> instead
        # of emitting a <vulp:tool> call, the loop would silently end. We
        # retry ONCE with a system reminder that pins the rule.
        if (
            not parsed.tool_calls
            and any(HALLUCINATED_TOOL_RESULT in e for e in parsed.parse_errors)
        ):
            api_messages.append({"role": "assistant", "content": raw_text})
            api_messages.append({
                "role": "user",
                "content": (
                    "<system-reminder>\n"
                    "You emitted a <vulp:tool_result> block. Only the harness "
                    "produces tool results — that block was fabricated and "
                    "discarded. The user did NOT see it.\n\n"
                    "To actually run a tool, emit <vulp:tool name=\"...\"> "
                    "with <vulp:arg> children. Reissue the call now using the "
                    "correct format.\n"
                    "</system-reminder>"
                ),
            })
            payload["data"]["solicitacao"]["messages"] = api_messages
            try:
                resp = await self._client.post(
                    self.endpoint, headers=headers, json=payload
                )
                resp.raise_for_status()
                data = resp.json().get("data")
                if isinstance(data, str) and data:
                    raw_text = data
                    parsed = parse_response(raw_text)
            except (httpx.HTTPError, ValueError):
                # If the retry itself fails, fall through with the original
                # parsed result so the user at least gets the parse error.
                pass

        if parsed.text:
            yield StreamChunk(type="text", delta=parsed.text)

        schema_by_name = {
            t.get("name"): t.get("input_schema", {})
            for t in tools
            if isinstance(t, dict)
        }
        for tc in parsed.tool_calls:
            schema = schema_by_name.get(tc.name)
            if isinstance(schema, dict):
                tc.arguments = _coerce_text_args(tc.arguments, schema)
            yield StreamChunk(type="tool_call", tool_call=tc)

        if parsed.parse_errors and not parsed.tool_calls:
            yield StreamChunk(
                type="text",
                delta=(
                    "\n\n(protocol parse errors — please re-emit using the "
                    "exact <vulp:tool>/<vulp:arg>/<vulp:content> format)"
                ),
            )

        yield StreamChunk(
            type="usage",
            usage=Usage(
                input_tokens=self._messages_tokens(api_messages),
                output_tokens=self._estimate_tokens(raw_text),
            ),
        )
        yield StreamChunk(
            type="stop",
            stop_reason="tool_use" if parsed.tool_calls else "end_turn",
            raw={"model_requested": model},
        )

    async def list_models(self) -> list[str]:
        return ["internal-llm-agentic"]
