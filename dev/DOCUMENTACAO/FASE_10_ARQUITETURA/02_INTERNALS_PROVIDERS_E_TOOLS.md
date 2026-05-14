# Tarefa 10.02 - Internals: Provider Translation + Tool Registry

**Status**: PENDENTE
**Fase**: 10 - Arquitetura
**Dependencias**: 10.01
**Bloqueia**: nada

---

## Objetivo

Criar `architecture/provider-translation.md` e
`architecture/tool-registry.md` explicando como cada provider traduz schemas
e como tools sao descobertas em runtime.

---

## Arquivos a criar

- `docs/architecture/provider-translation.md`
- `docs/architecture/tool-registry.md`

---

## Source de verdade

- `src/vulpcode/providers/*.py`
- `src/vulpcode/tools/base.py` — `@tool`, `TOOL_REGISTRY`
- `src/vulpcode/tools/__init__.py` — imports que registram

---

## Conteudo de `architecture/provider-translation.md`

### 1. Forma canonica

Mensagens em `Message` (Pydantic) com `role`, `content`, `tool_calls`,
`tool_call_id`, `name`. Tools como dict `{name, description, input_schema}`.

### 2. Schema de tool — traducao por provider

| Provider     | Forma                                                                        |
|--------------|------------------------------------------------------------------------------|
| Anthropic    | `{name, description, input_schema}` (igual ao canonico)                      |
| OpenAI       | `{type: "function", function: {name, description, parameters}}`              |
| Gemini       | `{function_declarations: [{name, description, parameters}]}`                 |
| Ollama       | igual OpenAI                                                                 |
| internal-llm | nao suporta — tools sao ignoradas com aviso textual                          |

### 3. Mensagens — traducao

Tabela de como `Message(role, content, tool_calls, tool_call_id, name)` e
mapeada para cada provider:

#### Anthropic

- `role="user/assistant"` -> direto
- `role="assistant"` com tool_calls -> content e lista de blocos `text` +
  `tool_use(id, name, input)`
- `role="tool"` -> `role="user"` com bloco `tool_result(tool_use_id, content)`
- `system` separado (parametro top-level)

#### OpenAI

- `role` direto
- `assistant` com tool_calls -> `tool_calls: [{id, type, function: {name,
  arguments: <json string>}}]`
- `tool` -> `{role: "tool", tool_call_id, content}`
- `system` como primeira mensagem

#### Gemini

- `role: user -> "user"`, `assistant -> "model"`, `tool -> "user" with function_response`
- `system` como `system_instruction` (parametro top-level)
- ATENCAO: usa `name` da tool para correlacionar request/response, nao `id`
- Tool call ids sintetizados como `gemini_<hex>`

#### Ollama

- Igual OpenAI mas via NDJSON

#### internal-llm

- Achata historico em flat list de `{role, content}`
- `role="tool"` vira `role="user"` com prefixo `[tool <name> result]`
- system como primeira mensagem
- Sem tool_calls

### 4. Streaming — como cada provider produz StreamChunk

Resumo das aggregadas (especialmente OpenAI/Anthropic):

- **Anthropic**: input_tokens em `RawMessageStartEvent`, text em
  `RawContentBlockDeltaEvent.text_delta`, tool args agregados via
  `input_json_delta` ate `RawContentBlockStopEvent`, stop_reason em
  `RawMessageDeltaEvent.delta.stop_reason`
- **OpenAI**: text em `delta.content`, tool_calls fragmentos por `index`
  acumulados em string ate `finish_reason in {tool_calls, stop, length}`,
  usage so se `stream_options={"include_usage": True}`
- **Gemini**: function_call vem completo (sem agregacao)
- **Ollama**: tool_calls completos por NDJSON line
- **internal-llm**: 1 chunk de text + 1 usage + 1 stop, sem streaming real

### 5. Wrapping de erros

Todo provider envolve excecoes do SDK em `ProviderError`. O agent loop captura
e emite `ErrorEvent`.

---

## Conteudo de `architecture/tool-registry.md`

### 1. Como tools sao registradas

```python
# src/vulpcode/tools/read.py
from vulpcode.tools.base import Tool, ToolResult, tool

@tool(name="Read", description="...", requires_confirm=False)
class ReadTool(Tool):
    class Input(BaseModel):
        file_path: str
        offset: int | None = None
        limit: int | None = None

    async def run(self, args):
        # ... logic ...
        return ToolResult(output="...")
```

O decorator `@tool`:
1. Valida que e subclass de `Tool` e tem `Input` nested.
2. Seta `_tool_name`, `_tool_description`, `_requires_confirm` na classe.
3. Adiciona em `TOOL_REGISTRY[name] = cls`.
4. Rejeita nomes duplicados com `ValueError`.

### 2. Bootstrap do registry

`src/vulpcode/tools/__init__.py` faz imports explicitos:

```python
from vulpcode.tools import read as _read     # noqa
from vulpcode.tools import write as _write   # noqa
from vulpcode.tools import edit as _edit     # noqa
# ...
```

Esses imports executam o `@tool` decorator, populando o registry. Sem o import,
a tool nao aparece em `list_tools()`.

### 3. MCP tools

Adicionadas em runtime via `_make_tool_adapter` em `mcp/client.py`. Geram
classes Python dinamicamente (via `type()` + `@tool`) com nome qualificado
`mcp__<server>__<name>`.

### 4. Helpers publicos

```python
from vulpcode.tools import (
    TOOL_REGISTRY,        # dict[str, type[Tool]]
    Tool, ToolResult,     # ABCs
    tool,                 # decorator
    get_tool,             # lookup por nome
    list_tools,           # lista de classes
    clear_registry,       # so para testes
    execute_tool_call,    # convenience: parse + run + wrap errors
)
```

### 5. JSON Schema dos Inputs

Cada `Tool.to_schema()` retorna:

```json
{
  "name": "Read",
  "description": "Read a file...",
  "input_schema": { /* Pydantic model_json_schema() */ }
}
```

O `input_schema` e gerado automaticamente pelo Pydantic v2. Para ajustar
descricoes de campos, use `Field(description="...")` no Input model.

### 6. Decisoes de design

- **Decorator-based**: claro, declarativo, registro automatico ao import.
- **TOOL_REGISTRY global**: simples, mas tornaria multi-instancia complexo —
  hoje nao e problema.
- **Nested Input class**: forca cada tool a ter schema explicito (Pydantic),
  validacao automatica antes de `run`.

---

## Atualizar `mkdocs.yml`

Entradas ja foram adicionadas em 10.01. Nao mexer.

---

## INSTRUCAO CRITICA

- Para a tabela de traducao de mensagens, leia o `_msg_to_*` de cada
  provider e confirme.
- Para o registry de tools, mostre TODOS os imports em
  `src/vulpcode/tools/__init__.py` (e a unica fonte de truth do bootstrap).

---

## Etapas de Implementacao

### Etapa 1: Ler arquivos providers/*.py e tools/__init__.py
### Etapa 2: Criar 2 arquivos
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/architecture/provider-translation.md` criado
- [x] Tabela de traducao de schema de tool por provider
- [x] Subsecao por provider para traducao de mensagens (Anthropic, OpenAI, Gemini, Ollama, internal-llm)
- [x] Subsecao de streaming agregation por provider
- [x] `docs/architecture/tool-registry.md` criado
- [x] Explicacao do `@tool` decorator
- [x] Imports explicitos em `__init__.py` mencionados
- [x] MCP tools dinamicas explicadas
- [x] Decisoes de design listadas
- [x] `mkdocs build` continua passando

---

**End of Specification**
