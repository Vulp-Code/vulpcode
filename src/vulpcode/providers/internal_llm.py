"""Provider for an internal corporate /chatCompletion endpoint.

This provider talks to an internal LLM microservice that exposes a JSON-RPC-ish
endpoint. It does NOT support streaming, tool calling or vision — the endpoint
returns the full assistant text in a single response.

Configuration (none of the values are hardcoded — pass via config.toml or env
vars; the library has no built-in URL or UUID):

    [providers.internal-llm]
    base_url = "http://example.corp/chatCompletion"
    user_uuid = "00000000-0000-0000-0000-000000000000"
    timeout = 120.0
    max_retries = 3
    retry_delay = 5.0

Or via environment:

    INTERNAL_LLM_ENDPOINT=http://example.corp/chatCompletion
    INTERNAL_LLM_USER_UUID=00000000-0000-0000-0000-000000000000

Wire payload format (POST):

    {
      "data": {
        "solicitacao": {
          "messages": [{"role": "user", "content": "..."}, ...]
        },
        "config": {
          "temperature": 0.7,
          "max_tokens": 3000,
          "top_p": 0.95
        }
      }
    }

Headers: ``user-uuid: <uuid>``, ``Content-Type: application/json``.

Response: ``{"data": "<assistant text>"}``. ``data=null`` (with HTTP 200) means
the upstream LLM transiently failed — the provider retries.
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

import httpx

from vulpcode.providers.base import (
    Message,
    Provider,
    ProviderError,
    StreamChunk,
    Usage,
)


class InternalLLMProvider(Provider):
    """Internal corporate /chatCompletion endpoint provider (text-only)."""

    name = "internal-llm"

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
        return False

    def supports_vision(self) -> bool:
        return False

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _flatten_messages(
        messages: list[Message], system: str | None
    ) -> list[dict[str, str]]:
        """Convert canonical messages into the endpoint's flat list.

        - role="tool" becomes a user message tagged "[tool <name> result]" so the
          model can see the result even though tool calling isn't native.
        - role="assistant" with tool_calls keeps only the text part.
        """
        out: list[dict[str, str]] = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            if m.role == "tool":
                content = m.content if isinstance(m.content, str) else ""
                tag = m.name or m.tool_call_id or "tool"
                out.append(
                    {"role": "user", "content": f"[tool {tag} result]\n{content}"}
                )
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
                "internal-llm provider requires base_url (the endpoint URL). "
                "Set INTERNAL_LLM_ENDPOINT env var or "
                "providers.internal-llm.base_url in config.toml."
            )
        if not self.user_uuid:
            raise ProviderError(
                "internal-llm provider requires user_uuid. "
                "Set INTERNAL_LLM_USER_UUID env var or "
                "providers.internal-llm.user_uuid in config.toml."
            )

        if tools:
            yield StreamChunk(
                type="text",
                delta=(
                    "(note: this endpoint does not support tool calling; "
                    "tools were ignored)\n"
                ),
            )

        api_messages = self._flatten_messages(messages, system)

        max_tokens = kwargs.pop("max_tokens", 3000)
        temperature = kwargs.pop("temperature", 0.7)
        top_p = kwargs.pop("top_p", 0.95)

        payload: dict[str, Any] = {
            "data": {
                "solicitacao": {"messages": api_messages},
                "config": {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                },
            },
        }
        # The endpoint typically pins the deployment server-side and ignores
        # the requested model id; we still record it on the stop chunk so it
        # surfaces in debug logs and tracing.
        request_meta = {"model_requested": model}
        headers = {
            "user-uuid": self.user_uuid,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

        last_error: str | None = None
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
                    f"endpoint returned non-JSON response: {exc}"
                ) from exc

            content = (
                payload_response.get("data")
                if isinstance(payload_response, dict)
                else None
            )

            if content is None:
                last_error = (
                    f"endpoint returned data=null (attempt "
                    f"{attempt + 1}/{self.max_retries})"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise ProviderError(last_error)

            if not isinstance(content, str):
                content = str(content)

            yield StreamChunk(type="text", delta=content)
            yield StreamChunk(
                type="usage",
                usage=Usage(output_tokens=len(content.split())),
            )
            yield StreamChunk(
                type="stop", stop_reason="end_turn", raw=request_meta
            )
            return

        raise ProviderError(
            last_error or "internal-llm provider failed after retries"
        )

    async def list_models(self) -> list[str]:
        return ["internal-llm"]
