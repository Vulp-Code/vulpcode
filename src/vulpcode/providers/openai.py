"""OpenAI provider adapter (also covers DeepSeek, Groq, OpenRouter, LM Studio, vLLM)."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from vulpcode.providers.base import (
    Message,
    Provider,
    ProviderError,
    StreamChunk,
    ToolCall,
    Usage,
)


class OpenAIProvider(Provider):
    """Provider adapter for OpenAI and OpenAI-compatible endpoints.

    Backs the OpenAI provider as well as the compatible presets in
    :data:`vulpcode.providers.registry.OPENAI_COMPATIBLE_PRESETS`
    (DeepSeek, Groq, OpenRouter, LM Studio, vLLM). Differences between
    these are limited to ``base_url`` — the registry fills in a sensible
    default when the caller doesn't override it.

    Supports streaming, native tool calling, and vision (when the underlying
    model does).
    """

    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        **extra: Any,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url, timeout=timeout, **extra)
        self._client = AsyncOpenAI(
            api_key=api_key or "EMPTY",
            base_url=base_url,
            timeout=timeout,
        )

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    async def aclose(self) -> None:
        await self._client.close()

    @staticmethod
    def _msg_to_openai(msg: Message) -> dict[str, Any]:
        if msg.role == "tool":
            return {
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content if isinstance(msg.content, str) else "",
            }
        if msg.role == "assistant" and msg.tool_calls:
            return {
                "role": "assistant",
                "content": msg.content if isinstance(msg.content, str) else "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments or {}),
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        return {"role": msg.role, "content": msg.content}

    @staticmethod
    def _tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object"}),
                },
            }
            for t in tools
        ]

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        api_messages: list[dict[str, Any]] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend(self._msg_to_openai(m) for m in messages)
        api_tools = self._tools_to_openai(tools)

        params: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if api_tools:
            params["tools"] = api_tools
            params["tool_choice"] = "auto"
        params.update(kwargs)

        pending: dict[int, dict[str, Any]] = {}

        try:
            stream = await self._client.chat.completions.create(**params)
            async for chunk in stream:
                if getattr(chunk, "usage", None) is not None:
                    yield StreamChunk(
                        type="usage",
                        usage=Usage(
                            input_tokens=chunk.usage.prompt_tokens or 0,
                            output_tokens=chunk.usage.completion_tokens or 0,
                        ),
                    )
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta

                if delta and delta.content:
                    yield StreamChunk(type="text", delta=delta.content)

                if delta and delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = tc_chunk.index
                        slot = pending.setdefault(
                            idx, {"id": "", "name": "", "args": ""}
                        )
                        if tc_chunk.id:
                            slot["id"] = tc_chunk.id
                        if tc_chunk.function and tc_chunk.function.name:
                            slot["name"] = tc_chunk.function.name
                        if tc_chunk.function and tc_chunk.function.arguments:
                            slot["args"] += tc_chunk.function.arguments

                if choice.finish_reason in ("tool_calls", "stop", "length"):
                    for idx in sorted(pending):
                        slot = pending[idx]
                        try:
                            args = json.loads(slot["args"]) if slot["args"] else {}
                        except json.JSONDecodeError:
                            args = {}
                        yield StreamChunk(
                            type="tool_call",
                            tool_call=ToolCall(
                                id=slot["id"] or f"call_{idx}",
                                name=slot["name"],
                                arguments=args,
                            ),
                        )
                    pending.clear()

            yield StreamChunk(type="stop")
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"OpenAI stream failed: {exc}") from exc

    async def list_models(self) -> list[str]:
        try:
            resp = await self._client.models.list()
            return sorted(m.id for m in resp.data)
        except Exception:
            return []
