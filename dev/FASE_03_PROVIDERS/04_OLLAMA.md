# Tarefa 03.04 - Provider Ollama

**Status**: PENDENTE
**Fase**: 03 - Providers
**Dependencias**: 02.01 (Provider ABC)
**Bloqueia**: Nada

---

## Objetivo

Implementar `OllamaProvider` em `src/vulpcode/providers/ollama.py` usando o SDK
`ollama` (>=0.4) ou httpx direto contra `localhost:11434`. Suporta tool calling
em modelos compativeis (qwen2.5-coder, llama3.1, etc.) e streaming.

---

## Descricao Tecnica

### API do Ollama

O endpoint principal e `POST /api/chat` com payload similar ao OpenAI mas:
- `messages`: lista de `{"role", "content", "tool_calls"?, "tool_call_id"?}`
- `tools`: lista de `{"type": "function", "function": {...}}` (igual OpenAI)
- `stream: true` -> resposta NDJSON, uma linha por chunk
- Cada chunk: `{"model", "message": {"role", "content", "tool_calls"?}, "done": bool, ...}`
- `tool_calls` no message vem completo (nao fragmentado por delta) — diferente do OpenAI

### Estrutura

**`src/vulpcode/providers/ollama.py`**:

```python
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
    name = "ollama"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 300.0,  # local models can be slower
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
        return True  # depends on model; we leave to runtime

    def supports_vision(self) -> bool:
        return True  # llava and others

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
        # Pass extra options like temperature via kwargs into options
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
                            yield StreamChunk(type="tool_call", tool_call=ToolCall(
                                id=tc.get("id") or f"ollama_{uuid.uuid4().hex[:8]}",
                                name=fn.get("name", ""),
                                arguments=args or {},
                            ))

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
```

---

## INSTRUCAO CRITICA

- O Ollama nao tem API key — ignoramos `api_key` (pode ser None).
- `base_url` default e `http://localhost:11434`. Permitir override para Ollama remoto.
- O endpoint `/api/chat` ja suporta tools desde o release 0.3.x do Ollama, mas o
  modelo precisa ser compativel (qwen2.5-coder, llama3.1, mistral, etc.).
- Resposta e NDJSON: uma linha JSON por chunk. Usar `aiter_lines()` do httpx.
- `tool_calls` chega COMPLETO em um unico chunk (nao fragmentado), entao nao
  precisamos agregar como no OpenAI.
- `arguments` pode vir como string JSON ou como dict — tratar ambos.
- `done: true` no ultimo chunk traz `eval_count` (output tokens) e `prompt_eval_count`
  (input tokens).
- Timeout maior por padrao (300s) — modelos locais podem demorar mais.
- Usar httpx direto (nao o SDK ollama-python) para ter streaming async confiavel.

---

## Etapas de Implementacao

### Etapa 1: Criar `providers/ollama.py`

Conteudo conforme acima.

### Etapa 2: Criar `tests/test_providers/test_ollama.py`

```python
"""Tests for OllamaProvider (translation only)."""
import json
import pytest

from vulpcode.providers import Message, ToolCall
from vulpcode.providers.ollama import OllamaProvider


def test_supports_tools_and_vision():
    p = OllamaProvider()
    assert p.supports_tools() is True
    assert p.supports_vision() is True


def test_default_base_url():
    p = OllamaProvider()
    assert p.base_url == "http://localhost:11434"


def test_translate_user_message():
    p = OllamaProvider()
    out = p._msg_to_ollama(Message(role="user", content="hi"))
    assert out == {"role": "user", "content": "hi"}


def test_translate_assistant_with_tool_calls():
    p = OllamaProvider()
    msg = Message(
        role="assistant",
        content="ok",
        tool_calls=[ToolCall(id="t1", name="Read", arguments={"file_path": "/a"})],
    )
    out = p._msg_to_ollama(msg)
    assert out["tool_calls"][0]["function"]["name"] == "Read"
    assert out["tool_calls"][0]["function"]["arguments"] == {"file_path": "/a"}


def test_translate_tool_message():
    p = OllamaProvider()
    out = p._msg_to_ollama(Message(role="tool", tool_call_id="t1", content="42"))
    assert out["role"] == "tool"
    assert out["tool_call_id"] == "t1"
    assert out["content"] == "42"


def test_tools_translation():
    p = OllamaProvider()
    out = p._tools_to_ollama([{"name": "Read", "description": "r", "input_schema": {"type": "object"}}])
    assert out[0]["type"] == "function"
    assert out[0]["function"]["name"] == "Read"
```

### Etapa 3: Rodar testes

```bash
pytest tests/test_providers/test_ollama.py -v
```

Todos passam.

---

## Criterios de Aceite

- [x] `src/vulpcode/providers/ollama.py` implementa `OllamaProvider`
- [x] Default `base_url = "http://localhost:11434"`, override via parametro
- [x] Traduz mensagens canonicas para formato `/api/chat` do Ollama
- [x] Traduz tools canonicas para `{"type": "function", "function": {...}}`
- [x] Streaming consome NDJSON via `httpx.AsyncClient.stream`
- [x] Emite `text`, `tool_call`, `usage`, `stop` chunks
- [x] `arguments` aceita string JSON ou dict
- [x] `list_models()` consome `/api/tags`
- [x] Erros envolvidos em `ProviderError`
- [x] `tests/test_providers/test_ollama.py` com >=6 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Ollama nao rodando localmente | Alta | Baixo | Testes nao chamam endpoint real |
| Modelo escolhido nao suporta tool calling | Alta | Medio | Documentar em /models e na config |
| API do Ollama muda | Baixa | Medio | Usar httpx direto, nao depender do SDK |

---

**End of Specification**
