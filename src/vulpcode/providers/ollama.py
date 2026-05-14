"""Ollama provider adapter (talks to localhost:11434 by default)."""
from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator

import httpx

from vulpcode.providers.base import (
    Message,
    Provider,
    ProviderError,
    StreamChunk,
    ToolCall,
    Usage,
)


class OllamaProvider(Provider):
    """Provider adapter for a local Ollama server.

    Talks to the Ollama HTTP API (default ``http://localhost:11434``) over
    ``httpx``. Supports streaming and native tool calling on models that
    advertise it (e.g. ``llama3.1``, ``qwen2.5``, ``mistral-nemo``). Vision
    is supported on multimodal models like ``llava``.

    No API key is required — ``api_key`` is accepted for interface symmetry
    but ignored.
    """

    name = "ollama"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 300.0,
        **extra: Any,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url or "http://localhost:11434",
            timeout=timeout,
            **extra,
        )
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _msg_to_ollama(msg: Message) -> dict[str, Any]:
        if msg.role == "tool":
            return {
                "role": "tool",
                "content": msg.content if isinstance(msg.content, str) else "",
                "tool_call_id": msg.tool_call_id or "",
            }
        if msg.role == "assistant" and msg.tool_calls:
            return {
                "role": "assistant",
                "content": msg.content if isinstance(msg.content, str) else "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments or {}},
                    }
                    for tc in msg.tool_calls
                ],
            }
        return {"role": msg.role, "content": msg.content if isinstance(msg.content, str) else ""}

    @staticmethod
    def _tools_to_ollama(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        api_messages.extend(self._msg_to_ollama(m) for m in messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = self._tools_to_ollama(tools)
        if kwargs:
            payload.setdefault("options", {}).update(kwargs)

        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg = evt.get("message") or {}
                    text = msg.get("content")
                    if text:
                        yield StreamChunk(type="text", delta=text)

                    tool_calls = msg.get("tool_calls")
                    if tool_calls:
                        for tc in tool_calls:
                            fn = tc.get("function") or {}
                            args = fn.get("arguments")
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args) if args else {}
                                except json.JSONDecodeError:
                                    args = {}
                            yield StreamChunk(
                                type="tool_call",
                                tool_call=ToolCall(
                                    id=tc.get("id") or f"ollama_{uuid.uuid4().hex[:8]}",
                                    name=fn.get("name", ""),
                                    arguments=args or {},
                                ),
                            )

                    if evt.get("done"):
                        usage = Usage(
                            input_tokens=evt.get("prompt_eval_count", 0) or 0,
                            output_tokens=evt.get("eval_count", 0) or 0,
                        )
                        yield StreamChunk(type="usage", usage=usage)
                yield StreamChunk(type="stop")
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama stream failed: {exc}") from exc

    async def list_models(self) -> list[str]:
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return sorted(m.get("name", "") for m in data.get("models", []))
        except httpx.HTTPError:
            return []
