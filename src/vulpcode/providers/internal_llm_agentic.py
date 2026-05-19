"""Provider for an internal corporate /chatCompletion endpoint with text-based tool calling.

Wraps the same transport as InternalLLMProvider but adds an XML-ish text protocol
on top so tool calls work even though the endpoint has no native tool_use field.
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

import httpx

from vulpcode.providers._text_tool_protocol import (
    parse_response,
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


class InternalLLMAgenticProvider(Provider):
    """Internal /chatCompletion endpoint + text-based tool calling shim."""

    name = "internal-llm-agentic"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        user_uuid: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        **extra: Any,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url, timeout=timeout, **extra)
        self.endpoint = base_url
        self.user_uuid = user_uuid
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client = httpx.AsyncClient(timeout=timeout)

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

    @staticmethod
    def _flatten(messages: list[Message]) -> list[dict[str, str]]:
        """Convert canonical messages for the endpoint.

        - role="tool" -> user message containing <vulp:tool_result>...</vulp:tool_result>
        - role="assistant" with tool_calls -> keep only the text part (the XML was the text)
        """
        out: list[dict[str, str]] = []
        for m in messages:
            if m.role == "tool":
                body = m.content if isinstance(m.content, str) else ""
                is_err = body.startswith("Error:")
                envelope = render_tool_result(
                    name=m.name or "unknown",
                    call_id=m.tool_call_id or "unknown",
                    is_error=is_err,
                    body=body[len("Error:"):].strip() if is_err else body,
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

        max_tokens = kwargs.pop("max_tokens", 3000)
        temperature = kwargs.pop("temperature", 0.3)
        top_p = kwargs.pop("top_p", 0.95)

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

        parsed = parse_response(raw_text)

        if parsed.text:
            yield StreamChunk(type="text", delta=parsed.text)

        for tc in parsed.tool_calls:
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
            usage=Usage(output_tokens=len(raw_text.split())),
        )
        yield StreamChunk(
            type="stop",
            stop_reason="tool_use" if parsed.tool_calls else "end_turn",
            raw={"model_requested": model},
        )

    async def list_models(self) -> list[str]:
        return ["internal-llm-agentic"]
