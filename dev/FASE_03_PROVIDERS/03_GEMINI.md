# Tarefa 03.03 - Provider Gemini

**Status**: PENDENTE
**Fase**: 03 - Providers
**Dependencias**: 02.01 (Provider ABC)
**Bloqueia**: Nada

---

## Objetivo

Implementar `GeminiProvider` em `src/vulpcode/providers/gemini.py` usando o SDK
`google-genai`. Suporta tool calling nativo via `function_declarations` e streaming.

---

## Descricao Tecnica

### Mapeamento canonico -> Gemini

**Mensagens** (Gemini usa "contents" com "parts"):
- `Message(role="system", ...)` -> `system_instruction` (parametro top-level, NAO em contents)
- `Message(role="user", content="hi")` -> `{"role": "user", "parts": [{"text": "hi"}]}`
- `Message(role="assistant", content="...", tool_calls=[...])` ->
  `{"role": "model", "parts": [{"text": "..."}, {"function_call": {"name": ..., "args": {...}}}]}`
- `Message(role="tool", tool_call_id, content)` ->
  `{"role": "user", "parts": [{"function_response": {"name": <tool_name>, "response": {"result": <content>}}}]}`

**ATENCAO**: o Gemini nao usa `tool_call_id` — relaciona request/response pelo `name`.
Manter um mapa interno se necessario, mas a especificacao oficial e `name`-based.

**Tools**:
- Canonico `{"name", "description", "input_schema"}` ->
  `{"function_declarations": [{"name": ..., "description": ..., "parameters": <input_schema>}]}`
- O `parameters` precisa ter `type: "OBJECT"` (uppercase no Gemini), mas o SDK
  recente aceita o JSON Schema padrao tambem.

**Streaming events**:
- `client.aio.models.generate_content_stream(...)` retorna AsyncIterator de chunks.
- Cada chunk tem `chunk.candidates[0].content.parts`.
- `parts[i].text` -> texto -> emite `StreamChunk(type="text", delta=...)`
- `parts[i].function_call` -> tool call (vem completo, nao fragmentado) ->
  emite `StreamChunk(type="tool_call", tool_call=ToolCall(...))` com id sintetizado.
- `chunk.usage_metadata` -> emite `StreamChunk(type="usage", ...)` no final.

### Estrutura

**`src/vulpcode/providers/gemini.py`**:

```python
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
            return None  # handled separately as system_instruction
        if msg.role == "tool":
            # Use the tool name embedded in tool_call_id IF we recorded it,
            # otherwise fall back to a placeholder. The agent MUST set msg.name
            # to the tool name in addition to tool_call_id.
            tool_name = msg.name or msg.tool_call_id or "tool"
            return {
                "role": "user",
                "parts": [{
                    "function_response": {
                        "name": tool_name,
                        "response": {"result": msg.content if isinstance(msg.content, str) else ""},
                    },
                }],
            }
        if msg.role == "assistant":
            parts: list[dict[str, Any]] = []
            if isinstance(msg.content, str) and msg.content:
                parts.append({"text": msg.content})
            for tc in (msg.tool_calls or []):
                parts.append({"function_call": {"name": tc.name, "args": tc.arguments or {}}})
            return {"role": "model", "parts": parts}
        # user
        return {"role": "user", "parts": [{"text": msg.content if isinstance(msg.content, str) else ""}]}

    @staticmethod
    def _tools_to_gemini(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not tools:
            return []
        return [{
            "function_declarations": [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object"}),
                }
                for t in tools
            ]
        }]

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
                if chunk.usage_metadata is not None:
                    um = chunk.usage_metadata
                    yield StreamChunk(type="usage", usage=Usage(
                        input_tokens=getattr(um, "prompt_token_count", 0) or 0,
                        output_tokens=getattr(um, "candidates_token_count", 0) or 0,
                    ))
                if not chunk.candidates:
                    continue
                cand = chunk.candidates[0]
                if cand.content is None or not cand.content.parts:
                    continue
                for part in cand.content.parts:
                    if getattr(part, "text", None):
                        yield StreamChunk(type="text", delta=part.text)
                    fc = getattr(part, "function_call", None)
                    if fc is not None:
                        yield StreamChunk(type="tool_call", tool_call=ToolCall(
                            id=f"gemini_{uuid.uuid4().hex[:8]}",
                            name=fc.name,
                            arguments=dict(fc.args or {}),
                        ))
            yield StreamChunk(type="stop")
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
```

---

## INSTRUCAO CRITICA

- **`tool_call_id` vs `name`**: Gemini relaciona request/response por `name`, nao
  por id. O agente DEVE setar `msg.name` para o nome da tool ao construir a
  mensagem `role="tool"`. Documentar isto na FASE 08 (agent loop). Por seguranca,
  fazer fallback para `msg.tool_call_id` ou "tool".
- O id do tool call e sintetizado pelo provider — o Gemini nao retorna id, entao
  geramos `gemini_<hex>` para uso interno.
- `system_instruction` e parametro de `GenerateContentConfig`, NAO uma mensagem
  no `contents`.
- O SDK pode ter mudado entre versoes. Use `from google import genai; genai.Client(...)`
  e `client.aio.models.generate_content_stream(...)`. Se a API mudou, ajustar.
- `parameters` no `function_declarations` aceita JSON Schema padrao na versao
  recente — nao precisa converter para o tipo OBJECT enum.

---

## Etapas de Implementacao

### Etapa 1: Criar `providers/gemini.py`

Conteudo conforme acima.

### Etapa 2: Criar `tests/test_providers/test_gemini.py`

```python
"""Tests for GeminiProvider (translation only)."""
import pytest

pytest.importorskip("google.genai")

from vulpcode.providers import Message, ToolCall
from vulpcode.providers.gemini import GeminiProvider


def test_supports_tools_and_vision():
    p = GeminiProvider(api_key="test")
    assert p.supports_tools() is True
    assert p.supports_vision() is True


def test_translate_user_message():
    p = GeminiProvider(api_key="test")
    out = p._msg_to_gemini(Message(role="user", content="hi"))
    assert out["role"] == "user"
    assert out["parts"] == [{"text": "hi"}]


def test_translate_assistant_with_tool_calls():
    p = GeminiProvider(api_key="test")
    msg = Message(
        role="assistant",
        content="ok",
        tool_calls=[ToolCall(id="t1", name="Read", arguments={"file_path": "/a"})],
    )
    out = p._msg_to_gemini(msg)
    assert out["role"] == "model"
    assert any("function_call" in p_ for p_ in out["parts"])


def test_translate_tool_response():
    p = GeminiProvider(api_key="test")
    msg = Message(role="tool", tool_call_id="t1", name="Read", content="42")
    out = p._msg_to_gemini(msg)
    assert out["parts"][0]["function_response"]["name"] == "Read"
    assert out["parts"][0]["function_response"]["response"]["result"] == "42"


def test_system_message_is_skipped_in_contents():
    p = GeminiProvider(api_key="test")
    out = p._msg_to_gemini(Message(role="system", content="be brief"))
    assert out is None


def test_tools_translation():
    p = GeminiProvider(api_key="test")
    out = p._tools_to_gemini([{"name": "Read", "description": "r", "input_schema": {"type": "object"}}])
    assert out[0]["function_declarations"][0]["name"] == "Read"
```

### Etapa 3: Rodar testes

```bash
pytest tests/test_providers/test_gemini.py -v
```

Todos passam.

---

## Criterios de Aceite

- [x] `src/vulpcode/providers/gemini.py` implementa `GeminiProvider`
- [x] Traduz mensagens (user, assistant com function_call, tool com function_response)
- [x] System prompt e passado como `system_instruction` (nao no contents)
- [x] Traduz tools canonicas para `function_declarations`
- [x] Streaming emite `text`, `tool_call`, `usage`, `stop` chunks
- [x] Tool call ids sao sintetizados (`gemini_<hex>`)
- [x] Erros envolvidos em `ProviderError`
- [x] `tests/test_providers/test_gemini.py` com >=5 testes, todos passando (com `importorskip`)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| API do `google-genai` muda entre versoes | Alta | Alto | Pinar versao minima e isolar o uso |
| `tool_call_id` perdido na traducao | Alta | Medio | Setar `msg.name` no agent loop ao montar role="tool" |
| `function_call.args` vem como `Mapping` opaco | Media | Baixo | Forcar `dict(...)` |

---

**End of Specification**
