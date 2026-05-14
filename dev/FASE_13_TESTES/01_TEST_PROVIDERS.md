# Tarefa 13.01 - Testes End-to-End de Providers

**Status**: PENDENTE
**Fase**: 13 - Testes
**Dependencias**: Todas as fases 03 (providers) e 08 (agent)
**Bloqueia**: Nada

---

## Objetivo

Testes de integracao mais completos para os providers, usando Provider mocks
que simulam streaming completo. Isto vai alem dos testes unitarios de traducao
da FASE 03.

---

## Descricao Tecnica

### O que falta cobrir

Apos as fases 03.01-03.05, cada provider tem testes unitarios de traducao
(translation only). Faltam:

1. **Stream completo simulado**: simular chunks SSE/NDJSON crus e verificar que
   o provider emite `StreamChunk` corretos.
2. **Tool calls fragmentados (OpenAI)**: validar agregacao por index.
3. **Tool args JSON malformado**: validar fallback.
4. **Erros de rede**: validar `ProviderError` levantado.
5. **Round-trip via Agent + Provider mock**: ja testado em 08, mas duplicar com
   variacoes (tool denied, multi-tool calls, etc.).

### Estrutura de testes

**`tests/test_providers/test_anthropic_stream.py`** (novo):

```python
"""Stream-level tests for AnthropicProvider with mocked SDK."""
from unittest.mock import AsyncMock, patch

import pytest

from vulpcode.providers.anthropic import AnthropicProvider
from vulpcode.providers.base import Message


class _FakeAnthropicEvents:
    """A scriptable async iterable yielding event objects with required attributes."""
    def __init__(self, events):
        self._events = list(events)

    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        for e in self._events:
            yield e


# Helper: build minimal event objects
class _Block:
    def __init__(self, type_, **kw): self.type = type_; self.__dict__.update(kw)

class _Delta:
    def __init__(self, type_, **kw): self.type = type_; self.__dict__.update(kw)

class _Evt:
    """Generic event holder. We tag with marker classes for isinstance checks."""

# We import the real types to satisfy isinstance checks in the provider code:
from anthropic.types import (  # type: ignore
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStopEvent,
)


# ... in practice, mocking the precise event objects is complex.
# Recommended approach: bypass the SDK by patching `messages.stream` with our async iter.

@pytest.mark.asyncio
async def test_anthropic_stream_text_only():
    p = AnthropicProvider(api_key="x")

    class FakeStream:
        async def __aenter__(self_): return _FakeAnthropicEvents([])
        async def __aexit__(self_, *args): return False

    # Patch the bound method to return FakeStream
    with patch.object(p._client.messages, "stream", return_value=FakeStream()):
        chunks = []
        async for c in p.stream(messages=[Message(role="user", content="hi")], tools=[], model="claude-x"):
            chunks.append(c)
        # Should at least yield a stop chunk
        assert any(c.type == "stop" for c in chunks)
```

**Observacao**: testes de stream Anthropic com eventos reais sao verbosos.
Apenas verificar que (a) o provider lida com stream vazio, (b) erros sao
envolvidos em `ProviderError`. O resto e coberto pelos testes de traducao.

**`tests/test_providers/test_openai_stream.py`** (novo):

```python
"""Stream-level test for OpenAIProvider tool_calls aggregation."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from vulpcode.providers.base import Message
from vulpcode.providers.openai import OpenAIProvider


def _make_chunk(text=None, tool_index=None, tc_id=None, tc_name=None, tc_args=None, finish=None, usage=None):
    delta = SimpleNamespace(
        content=text,
        tool_calls=[SimpleNamespace(
            index=tool_index,
            id=tc_id,
            function=SimpleNamespace(name=tc_name, arguments=tc_args),
        )] if tool_index is not None else None,
    )
    choices = [SimpleNamespace(delta=delta, finish_reason=finish)]
    return SimpleNamespace(choices=choices, usage=usage)


class _AsyncIter:
    def __init__(self, items): self.items = list(items)
    def __aiter__(self): return self
    async def __anext__(self):
        if not self.items: raise StopAsyncIteration
        return self.items.pop(0)


@pytest.mark.asyncio
async def test_openai_stream_aggregates_tool_call():
    chunks = [
        _make_chunk(tool_index=0, tc_id="t1", tc_name="Read"),
        _make_chunk(tool_index=0, tc_args='{"file_path":'),
        _make_chunk(tool_index=0, tc_args='"/abs"}'),
        _make_chunk(finish="tool_calls"),
        _make_chunk(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5)),
    ]
    p = OpenAIProvider(api_key="x")
    fake_create = AsyncMock(return_value=_AsyncIter(chunks))
    with patch.object(p._client.chat.completions, "create", new=fake_create):
        out = []
        async for c in p.stream(messages=[Message(role="user", content="x")], tools=[], model="gpt-4"):
            out.append(c)
    tool_calls = [c for c in out if c.type == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_call.name == "Read"
    assert tool_calls[0].tool_call.arguments == {"file_path": "/abs"}


@pytest.mark.asyncio
async def test_openai_stream_provider_error_on_exception():
    p = OpenAIProvider(api_key="x")
    async def fail(**kwargs): raise RuntimeError("boom")
    with patch.object(p._client.chat.completions, "create", new=AsyncMock(side_effect=RuntimeError("boom"))):
        from vulpcode.providers.base import ProviderError
        with pytest.raises(ProviderError):
            async for _ in p.stream(messages=[], tools=[], model="x"):
                pass
```

**`tests/test_providers/test_ollama_stream.py`** (novo):

```python
"""Stream-level test for OllamaProvider parsing NDJSON."""
import json
from unittest.mock import AsyncMock, patch
import pytest

from vulpcode.providers.base import Message
from vulpcode.providers.ollama import OllamaProvider


class _FakeStream:
    def __init__(self, lines): self._lines = list(lines)
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    def raise_for_status(self): pass
    async def aiter_lines(self):
        for ln in self._lines: yield ln


@pytest.mark.asyncio
async def test_ollama_parses_ndjson():
    lines = [
        json.dumps({"message": {"role": "assistant", "content": "hello"}, "done": False}),
        json.dumps({
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "t1",
                    "function": {"name": "Read", "arguments": {"file_path": "/a"}},
                }],
            },
            "done": True,
            "prompt_eval_count": 8,
            "eval_count": 3,
        }),
    ]
    p = OllamaProvider()
    with patch.object(p._client, "stream", return_value=_FakeStream(lines)):
        out = []
        async for c in p.stream(messages=[Message(role="user", content="x")], tools=[], model="qwen"):
            out.append(c)
    types = [c.type for c in out]
    assert "text" in types
    assert "tool_call" in types
    assert "usage" in types
    assert types[-1] == "stop"
```

---

## INSTRUCAO CRITICA

- Mockar SDKs com `unittest.mock.patch` apontando para o atributo do client.
- `SimpleNamespace` simula objetos com atributos de forma simples (sem precisar
  importar tipos do SDK).
- Para Anthropic, os tipos de evento sao classes especificas — instancie-os
  diretamente do SDK ou use as classes `_Block` / `_Delta` simplificadas com
  monkey-patching de `isinstance`. **Recomendado**: focar em testes de
  traducao/error, nao de eventos completos. Testes mais profundos de stream
  ficam para integracao real (smoke tests da FASE 14).
- O objetivo desta tarefa e cobertura — buscar passar a marca de 80% via
  `pytest --cov`.

---

## Etapas de Implementacao

### Etapa 1: Criar tests adicionais para OpenAI (com mock detalhado)

`tests/test_providers/test_openai_stream.py` — foco em agregacao de tool_calls.

### Etapa 2: Criar tests adicionais para Ollama (com mock httpx)

`tests/test_providers/test_ollama_stream.py` — foco em parsing NDJSON.

### Etapa 3: Tests minimos para Anthropic stream

`tests/test_providers/test_anthropic_stream.py` — foco em error handling.

### Etapa 4: Tests adicionais para Gemini

(Opcional) — mockar `client.aio.models.generate_content_stream`.

### Etapa 5: Rodar coverage

```bash
pip install pytest-cov
pytest --cov=src/vulpcode --cov-report=term-missing tests/test_providers/
```

Verificar cobertura >= 70% nos modulos `providers/*`.

---

## Criterios de Aceite

- [x] `tests/test_providers/test_openai_stream.py` criado (>=2 testes)
- [x] `tests/test_providers/test_ollama_stream.py` criado (>=1 teste)
- [x] `tests/test_providers/test_anthropic_stream.py` criado (>=1 teste, mesmo que minimo)
- [x] Todos os testes passam (`pytest tests/test_providers/`)
- [x] Cobertura de `src/vulpcode/providers/` >= 70% via `pytest --cov`

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Mocks frageis frente a mudanca de SDK | Alta | Medio | Pinar versoes; aceitar fragilidade |
| Cobertura abaixo de 70% | Media | Baixo | Adicionar testes de traducao adicional |

---

**End of Specification**
