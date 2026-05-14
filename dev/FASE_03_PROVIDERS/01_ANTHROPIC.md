# Tarefa 03.01 - Provider Anthropic

**Status**: PENDENTE
**Fase**: 03 - Providers
**Dependencias**: 02.01 (Provider ABC + tipos)
**Bloqueia**: Nada diretamente, mas FASE 08 precisa de pelo menos um provider funcional

---

## Objetivo

Implementar `AnthropicProvider` em `src/vulpcode/providers/anthropic.py` usando o SDK
oficial `anthropic` (>=0.40). O provider deve traduzir mensagens canonicas para o formato
Anthropic, fazer streaming via SSE, agregar tool calls que chegam fragmentados, e emitir
`StreamChunk` no formato canonico.

---

## Descricao Tecnica

### Mapeamento canonico -> Anthropic

**Mensagens**:
- Canonico `Message(role="user", content="hi")` -> `{"role": "user", "content": "hi"}`
- Canonico `Message(role="assistant", content="...", tool_calls=[...])` -> conteudo
  estruturado com blocos `{"type": "text", "text": ...}` e `{"type": "tool_use", "id", "name", "input"}`
- Canonico `Message(role="tool", tool_call_id="abc", content="result")` -> `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "abc", "content": "result"}]}`
- O `system` e passado como parametro top-level, NAO como mensagem.

**Tools**:
- Canonico `{"name", "description", "input_schema"}` -> Anthropic ja aceita esta forma
  diretamente. Apenas garantir que o JSON Schema esta no shape esperado pela Anthropic
  (object com properties).

**Streaming events**:
- `RawMessageStartEvent` -> ignorado (apenas metadata)
- `RawContentBlockStartEvent`:
  - bloco `text` -> nao emite ainda
  - bloco `tool_use` -> inicia agregacao em buffer interno keyed por `index`
- `RawContentBlockDeltaEvent`:
  - `text_delta` -> emite `StreamChunk(type="text", delta=...)`
  - `input_json_delta` -> append em buffer JSON do tool_use atual
- `RawContentBlockStopEvent`:
  - bloco `tool_use` -> parse JSON acumulado, emite `StreamChunk(type="tool_call", tool_call=ToolCall(...))`
- `RawMessageDeltaEvent` -> pode conter `usage` -> emite `StreamChunk(type="usage", usage=Usage(...))`
- `RawMessageStopEvent` -> emite `StreamChunk(type="stop")`

### Estrutura do arquivo

**`src/vulpcode/providers/anthropic.py`**:

```python
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
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content if isinstance(msg.content, str) else "",
                }],
            }
        if msg.role == "assistant" and msg.tool_calls:
            blocks: list[dict[str, Any]] = []
            if isinstance(msg.content, str) and msg.content:
                blocks.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                blocks.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                })
            return {"role": "assistant", "content": blocks}
        # plain text
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
        max_tokens = kwargs.pop("max_tokens", 4096)

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

        # tool_use buffer keyed by content block index
        pending_tool_calls: dict[int, dict[str, Any]] = {}

        try:
            async with self._client.messages.stream(**params) as stream:
                async for event in stream:
                    chunk = self._handle_event(event, pending_tool_calls)
                    if chunk is not None:
                        yield chunk
                # final usage from stream.get_final_message()? Already emitted via delta.
                yield StreamChunk(type="stop")
        except Exception as exc:
            raise ProviderError(f"Anthropic stream failed: {exc}") from exc

    def _handle_event(
        self,
        event: Any,
        pending: dict[int, dict[str, Any]],
    ) -> StreamChunk | None:
        if isinstance(event, RawContentBlockStartEvent):
            block = event.content_block
            if block.type == "tool_use":
                pending[event.index] = {
                    "id": block.id,
                    "name": block.name,
                    "json": "",
                }
            return None

        if isinstance(event, RawContentBlockDeltaEvent):
            delta = event.delta
            if delta.type == "text_delta":
                return StreamChunk(type="text", delta=delta.text)
            if delta.type == "input_json_delta":
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
                return StreamChunk(type="usage", usage=Usage(
                    output_tokens=getattr(usage, "output_tokens", 0) or 0,
                ))
            return None

        if isinstance(event, RawMessageStopEvent):
            return None  # actual "stop" emitted in stream() after async with

        return None

    async def list_models(self) -> list[str]:
        # The SDK does not expose a list endpoint; return curated list.
        return [
            "claude-opus-4-7",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        ]
```

---

## INSTRUCAO CRITICA

- Usar `AsyncAnthropic` (cliente async) — combina com o agente que e async.
- `messages.stream(...)` retorna um context manager — usar `async with`.
- Nao usar `messages.create(stream=True)` — a API streaming oficial do SDK e
  `messages.stream()`.
- O SDK pode receber um schema de tool com `input_schema` que tenha apenas
  `type: "object"` (sem properties). Garantir que sempre passamos `input_schema`
  valido (default `{"type": "object"}`).
- Para `tool_result`, o `content` pode ser string OU lista de blocos. Nesta v1
  enviamos sempre como string para simplicidade.
- Quando o agente envia sequencia `assistant(tool_calls) -> tool(result) -> ...`,
  precisamos garantir que o `assistant` venha com TODOS os tool_use blocks no
  array de content. A funcao `_msg_to_anthropic` ja faz isso.
- `list_models()` retorna lista hardcoded — a Anthropic API nao tem endpoint publico
  de listagem.

---

## Etapas de Implementacao

### Etapa 1: Criar `providers/anthropic.py`

Conteudo conforme acima.

### Etapa 2: Criar `tests/test_providers/test_anthropic.py`

Testes que NAO chamam a API real. Mockar `AsyncAnthropic.messages.stream` ou
testar apenas o codigo de traducao.

```python
"""Tests for AnthropicProvider (translation only — no real API calls)."""
import pytest

from vulpcode.providers import Message, ToolCall
from vulpcode.providers.anthropic import AnthropicProvider


def test_supports_tools_and_vision():
    p = AnthropicProvider(api_key="test")
    assert p.supports_tools() is True
    assert p.supports_vision() is True


def test_translate_user_message():
    p = AnthropicProvider(api_key="test")
    out = p._msg_to_anthropic(Message(role="user", content="hello"))
    assert out == {"role": "user", "content": "hello"}


def test_translate_assistant_with_tools():
    p = AnthropicProvider(api_key="test")
    msg = Message(
        role="assistant",
        content="thinking",
        tool_calls=[ToolCall(id="t1", name="Read", arguments={"file_path": "/a"})],
    )
    out = p._msg_to_anthropic(msg)
    assert out["role"] == "assistant"
    assert out["content"][0] == {"type": "text", "text": "thinking"}
    assert out["content"][1]["type"] == "tool_use"
    assert out["content"][1]["id"] == "t1"
    assert out["content"][1]["input"] == {"file_path": "/a"}


def test_translate_tool_result_message():
    p = AnthropicProvider(api_key="test")
    msg = Message(role="tool", tool_call_id="t1", content="42")
    out = p._msg_to_anthropic(msg)
    assert out["role"] == "user"
    assert out["content"][0]["type"] == "tool_result"
    assert out["content"][0]["tool_use_id"] == "t1"
    assert out["content"][0]["content"] == "42"


def test_tools_translation():
    p = AnthropicProvider(api_key="test")
    canonical = [{"name": "Read", "description": "reads", "input_schema": {"type": "object"}}]
    out = p._tools_to_anthropic(canonical)
    assert out[0]["name"] == "Read"
    assert out[0]["input_schema"] == {"type": "object"}


@pytest.mark.asyncio
async def test_list_models_is_curated():
    p = AnthropicProvider(api_key="test")
    models = await p.list_models()
    assert any("claude" in m for m in models)
```

### Etapa 3: Rodar testes

```bash
pytest tests/test_providers/test_anthropic.py -v
```

Todos passam.

---

## Criterios de Aceite

- [x] `src/vulpcode/providers/anthropic.py` implementa `AnthropicProvider`
- [x] Traduz `Message` canonico -> formato Anthropic (user, assistant com tool_use, tool_result)
- [x] Traduz tools canonicas (passa `name`, `description`, `input_schema`)
- [x] `stream()` consome eventos do SDK e emite `StreamChunk` canonicos
- [x] Agrega `input_json_delta` por block index ate `content_block_stop` para emitir tool_call completo
- [x] Emite `StreamChunk(type="usage", ...)` quando recebe usage no delta
- [x] Sempre emite `StreamChunk(type="stop")` no final
- [x] Erros do SDK sao envolvidos em `ProviderError`
- [x] `tests/test_providers/test_anthropic.py` com >=6 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Mudanca na API do SDK Anthropic | Media | Alto | Pinar `anthropic>=0.40` e revisar event types |
| input_json fragmentado em UTF-8 invalido | Baixa | Medio | Buffer string-level, parse so no fim |
| Timeout em streams longos | Media | Medio | `timeout` configurado no client |
| Tool args invalidos (json malformado) | Baixa | Medio | `try/except json.JSONDecodeError -> {}` |

---

**End of Specification**
