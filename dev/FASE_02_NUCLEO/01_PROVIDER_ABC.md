# Tarefa 02.01 - Provider ABC + Tipos de Mensagem

**Status**: PENDENTE
**Fase**: 02 - Nucleo
**Dependencias**: 01.01, 01.02
**Bloqueia**: FASE 03 (todos os providers)

---

## Objetivo

Definir os tipos canonicos (`Message`, `ToolCall`, `StreamChunk`) e a classe abstrata
`Provider` em `src/vulpcode/providers/base.py`. Esta abstracao e o que permite o
agente nao saber se esta falando com Claude, GPT-4 ou Llama no Ollama.

---

## Descricao Tecnica

**Arquivo a criar**: `/home/guhaase/projetos/vulpcode/src/vulpcode/providers/base.py`

### Tipos canonicos

```python
"""Provider abstraction: types and base class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Literal

from pydantic import BaseModel, Field


Role = Literal["system", "user", "assistant", "tool"]


class ToolCall(BaseModel):
    """Single tool call requested by the model."""
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """One turn of the conversation in canonical form."""
    role: Role
    content: str | list[dict[str, Any]] = ""
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None  # for role="tool"
    name: str | None = None  # optional message label


class Usage(BaseModel):
    """Token accounting per turn."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


ChunkType = Literal[
    "text",            # delta text
    "tool_call",       # complete tool call (after streaming aggregation)
    "tool_call_delta", # partial tool call (provider-specific, optional)
    "stop",            # end of generation
    "usage",           # token usage report
    "error",           # provider-side error
]


class StreamChunk(BaseModel):
    """A single event emitted during ``Provider.stream()``."""
    type: ChunkType
    delta: str | None = None
    tool_call: ToolCall | None = None
    usage: Usage | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None  # original event for debugging


class ProviderError(RuntimeError):
    """Raised on unrecoverable provider failures."""


class Provider(ABC):
    """Abstract base class for all model providers.

    Subclasses translate the canonical ``Message`` / tool schema to the provider
    native format and stream back ``StreamChunk`` events.
    """

    name: str  # set by subclass: "anthropic", "openai", "gemini", "ollama"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        **extra: Any,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.extra = extra

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        model: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a turn of the conversation.

        Args:
            messages: canonical message history (excluding system prompt).
            tools: list of canonical tool schemas (the form produced by
                ``Tool.to_schema()``). The provider MUST translate these to its
                native format.
            model: the model id in provider-native form (e.g. "claude-sonnet-4-7").
            system: system prompt string.
            **kwargs: provider-specific extras (temperature, max_tokens, ...).
        """
        raise NotImplementedError
        yield  # pragma: no cover - to satisfy AsyncIterator typing

    @abstractmethod
    def supports_tools(self) -> bool:
        """Whether the provider supports native tool calling."""

    @abstractmethod
    def supports_vision(self) -> bool:
        """Whether the provider/model accepts image inputs."""

    async def list_models(self) -> list[str]:
        """List models available to the configured account.

        Default implementation returns an empty list. Override when supported.
        """
        return []

    async def aclose(self) -> None:
        """Release any underlying resources (HTTP clients, etc.)."""
        return None

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"
```

### Tool Schema canonico

Tambem definir nesta tarefa o tipo do schema de tool que `Provider.stream()` recebe.
Ele e independente do `Tool` ABC (que vem na tarefa 02.02), mas a forma e fixada aqui:

```python
# Convencao: dict com chaves
# {
#     "name": str,
#     "description": str,
#     "input_schema": dict,  # JSON Schema (gerado por Pydantic)
# }
```

Cada subclasse de `Provider` traduz isto para o formato nativo:
- Anthropic: usa `name`, `description`, `input_schema` direto
- OpenAI: embrulha em `{"type": "function", "function": {"name", "description", "parameters"}}`
- Gemini: lista `{"function_declarations": [{"name", "description", "parameters"}]}`

### Atualizar `providers/__init__.py`

```python
"""Provider adapters and abstractions."""
from vulpcode.providers.base import (
    Message,
    Provider,
    ProviderError,
    StreamChunk,
    ToolCall,
    Usage,
)

__all__ = [
    "Message",
    "Provider",
    "ProviderError",
    "StreamChunk",
    "ToolCall",
    "Usage",
]
```

---

## INSTRUCAO CRITICA

- Os tipos sao Pydantic v2 — usar `Field(default_factory=...)` quando default e mutavel.
- `Message.content` e `str | list[dict]` para suportar conteudo multimodal (texto + imagens
  no formato Anthropic). Providers que nao suportam vision tratam apenas a forma string.
- `StreamChunk` carrega `raw` (dict opcional) com o evento original do provider para
  facilitar debug e potencial retry — providers devem preencher quando relevante mas
  nao e obrigatorio para todo evento.
- A abstracao `Provider` e generica: nao assume modelos especificos. O `model` e passado
  como string em cada chamada de `stream()`.
- `ProviderError` para erros recuperaveis vs. inesperados — providers devem levantar
  esta excecao em vez de errors crus do SDK quando faz sentido.
- Nao importar nenhum SDK de provider aqui (anthropic, openai, etc.) — `base.py` e neutro.

---

## Etapas de Implementacao

### Etapa 1: Criar `providers/base.py`

Conteudo conforme descrito acima.

### Etapa 2: Atualizar `providers/__init__.py`

Re-exportar os tipos publicos.

### Etapa 3: Criar `tests/test_providers/test_base.py`

```python
"""Tests for the canonical provider types and ABC."""
import pytest
from pydantic import ValidationError

from vulpcode.providers import Message, Provider, StreamChunk, ToolCall, Usage


def test_message_minimal() -> None:
    m = Message(role="user", content="hi")
    assert m.role == "user"
    assert m.content == "hi"
    assert m.tool_calls is None


def test_message_with_tool_calls() -> None:
    tc = ToolCall(id="t1", name="Read", arguments={"file_path": "/a"})
    m = Message(role="assistant", content="", tool_calls=[tc])
    assert m.tool_calls[0].name == "Read"


def test_message_invalid_role() -> None:
    with pytest.raises(ValidationError):
        Message(role="other", content="x")


def test_streamchunk_text() -> None:
    c = StreamChunk(type="text", delta="hello")
    assert c.delta == "hello"


def test_streamchunk_tool_call() -> None:
    tc = ToolCall(id="x", name="Bash", arguments={"command": "ls"})
    c = StreamChunk(type="tool_call", tool_call=tc)
    assert c.tool_call.name == "Bash"


def test_usage_defaults() -> None:
    u = Usage()
    assert u.input_tokens == 0


def test_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        Provider()  # type: ignore[abstract]
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_providers/test_base.py -v
```

Todos devem passar.

---

## Criterios de Aceite

- [x] `src/vulpcode/providers/base.py` criado com tipos `Message`, `ToolCall`, `Usage`, `StreamChunk`
- [x] `Provider` ABC definida com metodos `stream`, `supports_tools`, `supports_vision`, `list_models`, `aclose`
- [x] `ProviderError` exportada
- [x] `providers/__init__.py` re-exporta os tipos publicos
- [x] Tipos Pydantic validam corretamente (role invalido falha, etc.)
- [x] Provider nao pode ser instanciado diretamente (`TypeError`)
- [x] `tests/test_providers/test_base.py` criado e passa todos os testes

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Pydantic v2 quirks com Literal | Baixa | Baixo | Testar `validation` explicitamente |
| AsyncIterator + abstractmethod | Media | Medio | Padrao com `raise NotImplementedError; yield` |
| Tipos divergem dos providers reais | Media | Alto | Revisitar quando implementar cada provider |

---

**End of Specification**
