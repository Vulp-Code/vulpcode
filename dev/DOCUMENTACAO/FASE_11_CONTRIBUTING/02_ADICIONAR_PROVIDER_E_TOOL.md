# Tarefa 11.02 - Contributing: Adicionar Provider + Adicionar Tool

**Status**: PENDENTE
**Fase**: 11 - Contributing
**Dependencias**: 11.01
**Bloqueia**: nada

---

## Objetivo

Criar 2 paginas tutoriais que ensinam como estender o vulpcode com um provider
novo ou uma tool nova.

---

## Arquivos a criar

- `docs/contributing/add-provider.md`
- `docs/contributing/add-tool.md`

---

## Source de verdade

- `src/vulpcode/providers/base.py` — `Provider` ABC
- `src/vulpcode/providers/registry.py`
- `src/vulpcode/tools/base.py` — `Tool` ABC, `@tool`
- Exemplos: `src/vulpcode/providers/internal_llm.py`, `src/vulpcode/tools/read.py`

---

## Conteudo de `add-provider.md`

### Contexto

Voce quer suportar um novo modelo/API. 3 caminhos:

1. **OpenAI-compatible**: API que ja segue o padrao chat completions —
   apenas adicione um preset.
2. **Dedicado**: API com formato proprio — herde de `Provider`.
3. **Customizacao de existente**: subclass de um provider existente.

### Caminho 1 — OpenAI-compatible (mais facil)

Em `src/vulpcode/providers/registry.py`:

```python
OPENAI_COMPATIBLE_PRESETS = {
    ...
    "minha-empresa": "https://meu-llm.empresa.com/v1",
}
```

Em `src/vulpcode/config.py` (opcional, para env var):

```python
ENV_MAP = {
    ...
    "MINHA_EMPRESA_API_KEY": ("providers", "minha-empresa", "api_key"),
}
```

Em `src/vulpcode/app.py`:

```python
def _default_model_for(provider_name):
    return {
        ...
        "minha-empresa": "modelo-default",
    }.get(provider_name, "")
```

Adicionar testes em `tests/test_providers/test_registry.py`. Pronto.

### Caminho 2 — Provider dedicado

Crie `src/vulpcode/providers/<seu>.py`:

```python
"""Seu provider."""
from typing import Any, AsyncIterator
import httpx
from vulpcode.providers.base import (
    Message, Provider, ProviderError, StreamChunk, ToolCall, Usage
)


class SeuProvider(Provider):
    name = "seu"

    def __init__(self, api_key=None, base_url=None, timeout=120.0, **extra):
        super().__init__(api_key=api_key, base_url=base_url, timeout=timeout, **extra)
        self._client = httpx.AsyncClient(...)  # ou SDK oficial

    def supports_tools(self) -> bool: return True
    def supports_vision(self) -> bool: return False

    async def aclose(self):
        await self._client.aclose()

    async def stream(self, messages, tools, model, system=None, **kwargs):
        # 1. Traduzir messages canonicos -> formato do seu provider
        # 2. Traduzir tools canonicos -> formato do seu provider
        # 3. Chamar API com streaming
        # 4. Yield StreamChunk(type=...) por evento
        # 5. Yield StreamChunk(type="stop", stop_reason="...") no fim

        try:
            # ... seu codigo ...
            yield StreamChunk(type="text", delta="...")
            yield StreamChunk(type="stop", stop_reason="end_turn")
        except Exception as exc:
            raise ProviderError(f"...: {exc}") from exc

    async def list_models(self):
        return ["seu-modelo-1", "seu-modelo-2"]
```

Em `src/vulpcode/providers/registry.py`:

```python
from vulpcode.providers.seu import SeuProvider
_DEDICATED["seu"] = SeuProvider
```

Adicionar testes em `tests/test_providers/test_seu.py` (espelhe o padrao
de `test_internal_llm.py`):
- Tests de traducao (sem chamar API real)
- Tests de stream com mock
- Test de erros (4xx, 5xx, retry)
- Test de registry (`assert "seu" in list_provider_names()`)

### Checklist final

- [ ] Provider em `src/vulpcode/providers/<seu>.py`
- [ ] Registry atualizado
- [ ] `app.py` _default_model_for atualizado
- [ ] env vars (opcional) em `config.py`
- [ ] Tests >= 6 em `tests/test_providers/test_<seu>.py`
- [ ] Doc em `docs/providers/<seu>.md` (FASE 04 padrao)
- [ ] Atualizar `docs/providers/index.md` com nova linha na tabela
- [ ] Atualizar `mkdocs.yml` nav
- [ ] `pytest tests/` passa
- [ ] `mkdocs build --strict` passa

### Decisoes comuns

- **Streaming nao suportado pela API?**: yieldar 1 text chunk + 1 stop chunk.
  Veja `internal_llm.py` como exemplo.
- **Tool calling nao suportado?**: `supports_tools=False` e ignore tools com
  aviso textual no inicio do stream.
- **Auth nao-padrao (header custom)?**: passe `extra` no construtor (ex:
  `user_uuid`, `tenant_id`), guarde como atributo, use no header.

---

## Conteudo de `add-tool.md`

### Contexto

Voce quer adicionar uma tool que o LLM pode chamar (ex: enviar email, query SQL).

### Estrutura minima

Crie `src/vulpcode/tools/<sua>.py`:

```python
"""Sua tool."""
from pydantic import BaseModel
from vulpcode.tools.base import Tool, ToolResult, tool


@tool(
    name="SuaTool",
    description="Descricao curta — o LLM le isso para decidir quando usar.",
    requires_confirm=False,  # True se for destrutiva
)
class SuaTool(Tool):
    class Input(BaseModel):
        param1: str
        param2: int = 0
        flag: bool = False

    async def run(self, args: BaseModel) -> ToolResult:
        assert isinstance(args, SuaTool.Input)

        # ... logica ...

        if erro:
            return ToolResult(error="mensagem clara", is_error=True)

        return ToolResult(
            output="resultado em texto (sera enviado de volta ao LLM)",
            metadata={"k": "v"},  # opcional, fica disponivel mas nao vai ao LLM
        )
```

Em `src/vulpcode/tools/__init__.py`:

```python
from vulpcode.tools import sua as _sua  # noqa: F401  (registra)
```

### Boas praticas

- **`description` clara** — o LLM ve isso. Diga o que faz, nao como faz.
  Mau: "uses async httpx to send POST". Bom: "Send an email to a recipient".
- **`Input` enxuto** — minimize argumentos. Use `Field(description="...")` em
  cada campo para guiar o LLM.
- **`requires_confirm=True`** se: escreve em disco, executa shell, envia
  request externo, deleta dados.
- **Output curto** — o LLM cobra tokens por palavra. Truncar resultados longos.
- **Erros descritivos** — `ToolResult(error="...", is_error=True)` em vez de
  raise. O agente trata graciosamente.

### Tests

Em `tests/test_tools/test_sua.py`:

```python
import pytest
import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_sua_happy_path():
    cls = get_tool("SuaTool")
    res = await cls().run(cls.Input(param1="x"))
    assert not res.is_error
    assert "esperado" in res.output


@pytest.mark.asyncio
async def test_sua_invalid_input():
    cls = get_tool("SuaTool")
    with pytest.raises(Exception):
        cls.Input()  # missing required param1


def test_sua_registered():
    cls = get_tool("SuaTool")
    assert cls._tool_name == "SuaTool"
```

### Tools que precisam de estado entre chamadas

Use modulo-level dict (como `_TODO_STORE` em `todo.py`) ou patterns mais
sofisticados via attribute em sessao. Evite singletons globais quando possivel.

### Checklist final

- [ ] Tool em `src/vulpcode/tools/<sua>.py`
- [ ] Import em `tools/__init__.py`
- [ ] Tests em `tests/test_tools/test_<sua>.py`
- [ ] Doc em `docs/tools/<categoria>.md` (FASE 05)
- [ ] Atualizar `docs/tools/index.md` com nova linha na tabela
- [ ] `pytest tests/` passa

### Patterns avancados

- **Background work**: spawnar task asyncio (veja `_drain` em bash.py)
- **Stateful**: registry compartilhado (veja `_bash_registry.py`)
- **Permission tracking** com metadata custom

---

## Atualizar `mkdocs.yml`

As entradas ja foram adicionadas em 11.01. Nao mexer.

---

## INSTRUCAO CRITICA

- Os exemplos devem compilar/rodar — confira contra `Provider` ABC e `Tool`
  ABC reais.
- Mostre o decorator `@tool(name=..., description=..., requires_confirm=...)`
  com argumentos exatos.

---

## Etapas de Implementacao

### Etapa 1: Re-ler `Provider` e `Tool` ABCs
### Etapa 2: Criar 2 arquivos
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/contributing/add-provider.md` criado com 2 caminhos (OpenAI-compat e dedicado)
- [x] Esqueleto de provider dedicado completo (com stream, tradicao, retry)
- [x] Checklist final
- [x] `docs/contributing/add-tool.md` criado com esqueleto + boas praticas + tests
- [x] Checklist final tambem
- [x] `mkdocs build` continua passando

---

**End of Specification**
