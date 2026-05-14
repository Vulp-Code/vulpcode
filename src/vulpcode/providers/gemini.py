"""Google Gemini provider adapter."""
from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from google import genai
from google.genai import types as genai_types

from vulpcode.providers.base import (
    Message,
    Provider,
    ProviderError,
    StreamChunk,
    ToolCall,
    Usage,
)


class GeminiProvider(Provider):
    """Provider adapter for Google Gemini models.

    Uses the official ``google-genai`` SDK. Translates canonical messages
    into Gemini's ``contents`` / ``parts`` shape, including ``function_call``
    and ``function_response`` parts for tool execution. Supports streaming,
    tool calling, and vision.
    """

    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        **extra: Any,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url, timeout=timeout, **extra)
        self._client = genai.Client(api_key=api_key)

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    @staticmethod
    def _msg_to_gemini(msg: Message) -> dict[str, Any] | None:
        if msg.role == "system":
            return None
        if msg.role == "tool":
            tool_name = msg.name or msg.tool_call_id or "tool"
            return {
                "role": "user",
                "parts": [
                    {
                        "function_response": {
                            "name": tool_name,
                            "response": {
                                "result": msg.content if isinstance(msg.content, str) else ""
                            },
                        }
                    }
                ],
            }
        if msg.role == "assistant":
            parts: list[dict[str, Any]] = []
            if isinstance(msg.content, str) and msg.content:
                parts.append({"text": msg.content})
            for tc in msg.tool_calls or []:
                parts.append(
                    {"function_call": {"name": tc.name, "args": tc.arguments or {}}}
                )
            return {"role": "model", "parts": parts}
        return {
            "role": "user",
            "parts": [{"text": msg.content if isinstance(msg.content, str) else ""}],
        }

    @staticmethod
    def _tools_to_gemini(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not tools:
            return []
        return [
            {
                "function_declarations": [
                    {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {"type": "object"}),
                    }
                    for t in tools
                ]
            }
        ]

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        contents: list[dict[str, Any]] = []
        for m in messages:
            mapped = self._msg_to_gemini(m)
            if mapped is not None:
                contents.append(mapped)

        config: dict[str, Any] = {}
        if system:
            config["system_instruction"] = system
        gem_tools = self._tools_to_gemini(tools)
        if gem_tools:
            config["tools"] = gem_tools

        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=genai_types.GenerateContentConfig(**config) if config else None,
            )
            async for chunk in stream:
                if getattr(chunk, "usage_metadata", None) is not None:
                    um = chunk.usage_metadata
                    yield StreamChunk(
                        type="usage",
                        usage=Usage(
                            input_tokens=getattr(um, "prompt_token_count", 0) or 0,
                            output_tokens=getattr(um, "candidates_token_count", 0) or 0,
                        ),
                    )
                if not getattr(chunk, "candidates", None):
                    continue
                cand = chunk.candidates[0]
                if cand.content is None or not cand.content.parts:
                    continue
                for part in cand.content.parts:
                    text = getattr(part, "text", None)
                    if text:
                        yield StreamChunk(type="text", delta=text)
                    fc = getattr(part, "function_call", None)
                    if fc is not None:
                        yield StreamChunk(
                            type="tool_call",
                            tool_call=ToolCall(
                                id=f"gemini_{uuid.uuid4().hex[:8]}",
                                name=fc.name,
                                arguments=dict(fc.args or {}),
                            ),
                        )
            yield StreamChunk(type="stop")
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Gemini stream failed: {exc}") from exc

    async def list_models(self) -> list[str]:
        try:
            resp = await self._client.aio.models.list()
            return sorted(m.name for m in resp if hasattr(m, "name"))
        except Exception:
            return [
                "gemini-2.0-flash",
                "gemini-2.5-pro",
            ]
