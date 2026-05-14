# Tarefa 03.02 - Provider OpenAI (cobre DeepSeek, Groq, OpenRouter)

**Status**: PENDENTE
**Fase**: 03 - Providers
**Dependencias**: 02.01 (Provider ABC)
**Bloqueia**: Nada

---

## Objetivo

Implementar `OpenAIProvider` em `src/vulpcode/providers/openai.py` usando o SDK
oficial `openai` (>=1.50). O mesmo provider, parametrizado com `base_url`, atende
DeepSeek, Groq, OpenRouter, LM Studio e vLLM (todos OpenAI-compativeis).

---

## Descricao Tecnica

### Mapeamento canonico -> OpenAI

**Mensagens** (formato chat completions):
- `Message(role="system", content="...")` -> mas o `system` e passado como primeira
  mensagem `{"role": "system", "content": "..."}` (diferente do Anthropic).
- `Message(role="user", content="hi")` -> `{"role": "user", "content": "hi"}`
- `Message(role="assistant", content="...", tool_calls=[...])` ->
  `{"role": "assistant", "content": "...", "tool_calls": [{"id", "type": "function", "function": {"name", "arguments": <json string>}}]}`
- `Message(role="tool", tool_call_id="x", content="result")` ->
  `{"role": "tool", "tool_call_id": "x", "content": "result"}`

**Tools**:
- Canonico `{"name", "description", "input_schema"}` ->
  `{"type": "function", "function": {"name": ..., "description": ..., "parameters": <input_schema>}}`

**Streaming events**:
- `chat.completions.create(stream=True)` retorna `AsyncIterator[ChatCompletionChunk]`.
- Cada chunk tem `chunk.choices[0].delta` com:
  - `delta.content` -> texto incremental -> emite `StreamChunk(type="text", delta=...)`
  - `delta.tool_calls` -> lista de fragmentos com `index`, `id?`, `function.name?`,
    `function.arguments?` (string parcial). Agregar por `index` ate `finish_reason="tool_calls"`.
- `chunk.choices[0].finish_reason` -> quando "stop" ou "tool_calls", emitir tool_calls
  acumulados e depois `StreamChunk(type="stop")`.
- `chunk.usage` (apenas no ultimo chunk se `stream_options={"include_usage": True}`)
  -> emite `StreamChunk(type="usage", usage=...)`.

### Estrutura

**`src/vulpcode/providers/openai.py`**:

```python
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
            api_key=api_key or "EMPTY",  # local backends accept any key
            base_url=base_url,
            timeout=timeout,
        )

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        # depends on chosen model — leave True; agent can still send text-only
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

        # Aggregate tool calls by index
        pending: dict[int, dict[str, Any]] = {}

        try:
            stream = await self._client.chat.completions.create(**params)
            async for chunk in stream:
                if chunk.usage is not None:
                    yield StreamChunk(type="usage", usage=Usage(
                        input_tokens=chunk.usage.prompt_tokens or 0,
                        output_tokens=chunk.usage.completion_tokens or 0,
                    ))
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta

                if delta and delta.content:
                    yield StreamChunk(type="text", delta=delta.content)

                if delta and delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = tc_chunk.index
                        slot = pending.setdefault(idx, {"id": "", "name": "", "args": ""})
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
                        yield StreamChunk(type="tool_call", tool_call=ToolCall(
                            id=slot["id"] or f"call_{idx}",
                            name=slot["name"],
                            arguments=args,
                        ))
                    pending.clear()

            yield StreamChunk(type="stop")
        except Exception as exc:
            raise ProviderError(f"OpenAI stream failed: {exc}") from exc

    async def list_models(self) -> list[str]:
        try:
            resp = await self._client.models.list()
            return sorted(m.id for m in resp.data)
        except Exception:
            return []
```

### Aliases para outros backends

OpenRouter, DeepSeek, Groq sao apenas instancias parametrizadas. O `registry.py`
(tarefa 03.05) cuida de criar uma instancia de `OpenAIProvider` com `base_url`
correto baseado em config. Nao criamos subclasses separadas.

| Provider | base_url |
|---|---|
| openai | (default, omitir) |
| deepseek | https://api.deepseek.com/v1 |
| groq | https://api.groq.com/openai/v1 |
| openrouter | https://openrouter.ai/api/v1 |
| lmstudio | http://localhost:1234/v1 |
| vllm | http://localhost:8000/v1 |

---

## INSTRUCAO CRITICA

- Quando o usuario nao tem API key para backends locais (LM Studio, vLLM, Ollama
  via OpenAI-compat), passamos `api_key="EMPTY"` para satisfazer o SDK.
- O OpenAI SDK valida que `tool_calls` no historico tem o `function.arguments`
  como string JSON — por isso `json.dumps` na traducao.
- `stream_options={"include_usage": True}` e necessario para receber usage no
  ultimo chunk. Alguns backends nao-OpenAI ignoram isto silenciosamente, o que
  e OK — apenas nao haverá usage event.
- `delta.tool_calls` pode ter `index` 0, 1, 2... nao e necessariamente sequencial.
- Emitimos os tool_call chunks SO quando `finish_reason` e detectado, para garantir
  que o JSON dos arguments esteja completo.
- `list_models()` real funciona em OpenAI; em provedores que nao expoem o endpoint
  retornamos lista vazia (try/except).

---

## Etapas de Implementacao

### Etapa 1: Criar `providers/openai.py`

Conteudo conforme acima.

### Etapa 2: Criar `tests/test_providers/test_openai.py`

Foco em testes de traducao e suporte a flags.

```python
"""Tests for OpenAIProvider (translation only)."""
import json
import pytest

from vulpcode.providers import Message, ToolCall
from vulpcode.providers.openai import OpenAIProvider


def test_supports_tools_and_vision():
    p = OpenAIProvider(api_key="test")
    assert p.supports_tools() is True
    assert p.supports_vision() is True


def test_translate_user_message():
    p = OpenAIProvider(api_key="test")
    out = p._msg_to_openai(Message(role="user", content="hello"))
    assert out == {"role": "user", "content": "hello"}


def test_translate_assistant_with_tool_calls():
    p = OpenAIProvider(api_key="test")
    msg = Message(
        role="assistant",
        content="ok",
        tool_calls=[ToolCall(id="t1", name="Read", arguments={"file_path": "/a"})],
    )
    out = p._msg_to_openai(msg)
    assert out["tool_calls"][0]["id"] == "t1"
    assert out["tool_calls"][0]["function"]["name"] == "Read"
    assert json.loads(out["tool_calls"][0]["function"]["arguments"]) == {"file_path": "/a"}


def test_translate_tool_message():
    p = OpenAIProvider(api_key="test")
    out = p._msg_to_openai(Message(role="tool", tool_call_id="t1", content="42"))
    assert out["role"] == "tool"
    assert out["tool_call_id"] == "t1"
    assert out["content"] == "42"


def test_tools_translation():
    p = OpenAIProvider(api_key="test")
    canonical = [{"name": "Read", "description": "reads", "input_schema": {"type": "object", "properties": {}}}]
    out = p._tools_to_openai(canonical)
    assert out[0]["type"] == "function"
    assert out[0]["function"]["name"] == "Read"
    assert out[0]["function"]["parameters"] == {"type": "object", "properties": {}}


def test_supports_arbitrary_base_url():
    p = OpenAIProvider(api_key="test", base_url="https://api.deepseek.com/v1")
    assert "deepseek" in str(p._client.base_url)
```

### Etapa 3: Rodar testes

```bash
pytest tests/test_providers/test_openai.py -v
```

Todos passam.

---

## Criterios de Aceite

- [x] `src/vulpcode/providers/openai.py` implementa `OpenAIProvider`
- [x] Aceita `base_url` para uso com DeepSeek/Groq/OpenRouter/LM Studio/vLLM
- [x] Traduz mensagens canonicas para formato chat completions OpenAI
- [x] Traduz tools canonicas para `{"type": "function", "function": {...}}`
- [x] Streaming agrega tool_calls fragmentados por `index`
- [x] Emite `tool_call` chunks no `finish_reason` e `stop` no final
- [x] Suporta `include_usage` para reportar tokens
- [x] Erros do SDK envolvidos em `ProviderError`
- [x] `tests/test_providers/test_openai.py` com >=6 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Backend nao-OpenAI nao suporta `tool_choice` | Media | Medio | Permitir override via `kwargs` |
| API key vazia rejeitada pelo SDK | Baixa | Baixo | Default "EMPTY" |
| `tool_calls` chegam desordenados | Baixa | Medio | Aggregar por `index` (nao por chegada) |
| JSON arguments fragmentado e malformado | Media | Medio | `try/except` no parse final |

---

**End of Specification**
