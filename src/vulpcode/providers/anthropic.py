"""Anthropic provider adapter."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic
from anthropic.types import (
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStartEvent,
    RawMessageStopEvent,
)

from vulpcode.providers.base import (
    Message,
    Provider,
    ProviderError,
    StreamChunk,
    ToolCall,
    Usage,
)


class AnthropicProvider(Provider):
    """Provider adapter for Anthropic Claude models.

    Uses the official ``anthropic`` SDK with native streaming, tool calling,
    vision, and prompt-cache accounting. The ``api_key`` falls back to the
    ``ANTHROPIC_API_KEY`` environment variable when omitted.
    """

    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        **extra: Any,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url, timeout=timeout, **extra)
        self._client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    async def aclose(self) -> None:
        await self._client.close()

    # ---- translation ----

    @staticmethod
    def _msg_to_anthropic(msg: Message) -> dict[str, Any]:
        if msg.role == "tool":
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content if isinstance(msg.content, str) else "",
                    }
                ],
            }
        if msg.role == "assistant" and msg.tool_calls:
            blocks: list[dict[str, Any]] = []
            if isinstance(msg.content, str) and msg.content:
                blocks.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            return {"role": "assistant", "content": blocks}
        return {"role": msg.role, "content": msg.content}

    @staticmethod
    def _tools_to_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("input_schema", {"type": "object"}),
            }
            for t in tools
        ]

    # ---- main stream ----

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        anth_messages = [self._msg_to_anthropic(m) for m in messages]
        anth_tools = self._tools_to_anthropic(tools)
        max_tokens = kwargs.pop("max_tokens", 16384)

        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": anth_messages,
        }
        if system:
            params["system"] = system
        if anth_tools:
            params["tools"] = anth_tools
        params.update(kwargs)

        pending_tool_calls: dict[int, dict[str, Any]] = {}
        stop_reason: str | None = None

        try:
            async with self._client.messages.stream(**params) as stream:
                async for event in stream:
                    if isinstance(event, RawMessageDeltaEvent):
                        delta = getattr(event, "delta", None)
                        if delta is not None:
                            sr = getattr(delta, "stop_reason", None)
                            if sr:
                                stop_reason = sr
                    chunk = self._handle_event(event, pending_tool_calls)
                    if chunk is not None:
                        yield chunk
                yield StreamChunk(type="stop", stop_reason=stop_reason)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Anthropic stream failed: {exc}") from exc

    def _handle_event(
        self,
        event: Any,
        pending: dict[int, dict[str, Any]],
    ) -> StreamChunk | None:
        if isinstance(event, RawMessageStartEvent):
            usage = getattr(getattr(event, "message", None), "usage", None)
            if usage is not None:
                return StreamChunk(
                    type="usage",
                    usage=Usage(
                        input_tokens=getattr(usage, "input_tokens", 0) or 0,
                        output_tokens=getattr(usage, "output_tokens", 0) or 0,
                        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                        cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
                    ),
                )
            return None

        if isinstance(event, RawContentBlockStartEvent):
            block = event.content_block
            if getattr(block, "type", None) == "tool_use":
                pending[event.index] = {
                    "id": block.id,
                    "name": block.name,
                    "json": "",
                }
            return None

        if isinstance(event, RawContentBlockDeltaEvent):
            delta = event.delta
            delta_type = getattr(delta, "type", None)
            if delta_type == "text_delta":
                return StreamChunk(type="text", delta=delta.text)
            if delta_type == "input_json_delta":
                buf = pending.get(event.index)
                if buf is not None:
                    buf["json"] += delta.partial_json
            return None

        if isinstance(event, RawContentBlockStopEvent):
            buf = pending.pop(event.index, None)
            if buf is None:
                return None
            try:
                args = json.loads(buf["json"]) if buf["json"] else {}
            except json.JSONDecodeError:
                args = {}
            tc = ToolCall(id=buf["id"], name=buf["name"], arguments=args)
            return StreamChunk(type="tool_call", tool_call=tc)

        if isinstance(event, RawMessageDeltaEvent):
            usage = getattr(event, "usage", None)
            if usage is not None:
                return StreamChunk(
                    type="usage",
                    usage=Usage(
                        output_tokens=getattr(usage, "output_tokens", 0) or 0,
                    ),
                )
            return None

        if isinstance(event, RawMessageStopEvent):
            return None

        return None

    async def list_models(self) -> list[str]:
        return [
            "claude-opus-4-7",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        ]
