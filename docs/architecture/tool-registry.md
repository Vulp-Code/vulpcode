# Tool registry

As "tools" do Vulpcode (Read, Write, Bash, Grep, ...) sao classes Python
descobertas em **runtime** atraves de um registry global populado pelo
decorator `@tool`. Esta pagina mostra como o registry e bootstrapeado, como
adicionar uma tool nova, e como o MCP integra suas tools dinamicas no mesmo
mecanismo.

> Codigo-fonte: [`src/vulpcode/tools/base.py`](https://github.com/vulpcode/vulpcode/tree/main/src/vulpcode/tools/base.py)
> + [`src/vulpcode/tools/__init__.py`](https://github.com/vulpcode/vulpcode/tree/main/src/vulpcode/tools/__init__.py).
> Adapter MCP: [`src/vulpcode/mcp/client.py`](https://github.com/vulpcode/vulpcode/tree/main/src/vulpcode/mcp/client.py).

---

## 1. Como tools sao registradas

Cada tool nativa segue o mesmo padrao: subclasse de
[`Tool`][vulpcode.tools.base.Tool], `Input` aninhado em Pydantic, `run`
assincrono, e o decorator `@tool` para entrar no registry.

```python
# src/vulpcode/tools/read.py (exemplo)
from pydantic import BaseModel, Field
from vulpcode.tools.base import Tool, ToolResult, tool

@tool(
    name="Read",
    description="Read a file from the local filesystem.",
    requires_confirm=False,
)
class ReadTool(Tool):
    class Input(BaseModel):
        file_path: str = Field(description="Absolute path to the file.")
        offset: int | None = None
        limit: int | None = None

    async def run(self, args: "ReadTool.Input") -> ToolResult:
        # ... le o arquivo, monta a saida ...
        return ToolResult(output=...)
```

O que o decorator [`@tool`][vulpcode.tools.base.tool] faz, em ordem:

1. Verifica que `cls` e subclasse de `Tool` — se nao for, levanta `TypeError`.
2. Verifica que existe `cls.Input` e que ele e subclasse de
   `pydantic.BaseModel` — se nao, levanta `TypeError`.
3. Atribui `cls._tool_name`, `cls._tool_description`, `cls._requires_confirm`
   na classe.
4. Verifica que o `name` ainda **nao** esta no registry; se ja estiver,
   levanta `ValueError("Tool name '<name>' already registered")`.
5. Insere `TOOL_REGISTRY[name] = cls`.
6. Devolve a classe sem alteracoes adicionais.

A ordem de iteracao do `TOOL_REGISTRY` e **a ordem de insercao** —
exatamente a ordem em que as tools aparecem para o modelo na lista de
ferramentas disponiveis.

### `requires_confirm`

Quando `True`, o agent loop pergunta antes de executar a tool no modo de
permissao padrao. Operacoes destrutivas (`Bash`, `Write`, `Edit`) costumam
ter `requires_confirm=True`. Veja
[Modos de permissao](../user-guide/permission-modes.md).

---

## 2. Bootstrap do registry

`TOOL_REGISTRY` so e populado quando os modulos individuais sao importados —
o decorator roda **no import**. O Vulpcode dispara isso em
`src/vulpcode/tools/__init__.py`, que faz imports explicitos de cada modulo
de tool:

```python
# src/vulpcode/tools/__init__.py
from vulpcode.tools.base import (
    TOOL_REGISTRY, Tool, ToolResult,
    clear_registry, execute_tool_call, get_tool, list_tools, tool,
)

__all__ = [
    "TOOL_REGISTRY", "Tool", "ToolResult", "TodoItem",
    "clear_registry", "clear_todos", "execute_tool_call",
    "get_tool", "get_todos", "list_tools", "tool",
]

from vulpcode.tools import read as _read              # registers ReadTool
from vulpcode.tools import write as _write            # registers WriteTool
from vulpcode.tools import edit as _edit              # registers Edit, MultiEdit
from vulpcode.tools import glob as _glob              # registers GlobTool
from vulpcode.tools import grep as _grep              # registers GrepTool
from vulpcode.tools import bash as _bash              # registers BashTool
from vulpcode.tools import bash_background as _bash_bg  # BashOutput, KillBash
from vulpcode.tools import web as _web                # WebFetch, WebSearch
from vulpcode.tools import todo as _todo              # TodoWriteTool
from vulpcode.tools.todo import TodoItem, clear_todos, get_todos
from vulpcode.tools import task as _task              # TaskTool
from vulpcode.tools import notebook as _notebook      # NotebookEditTool
```

!!! warning "Sem import, sem tool"
    Uma tool **nao** entra em `list_tools()` se o modulo nunca for
    importado. Plugins externos devem garantir o import (no proprio
    `__init__.py`, em um entry point ou via `import` explicito do app
    consumidor) antes de iniciar o agent loop.

A consequencia pratica: `tools/__init__.py` e a **unica fonte de verdade**
do conjunto de tools nativas. Adicionar uma tool nova = um import a mais
nesse arquivo.

---

## 3. MCP tools — registro dinamico

Servidores MCP advertem suas proprias tools em runtime. O Vulpcode as
incorpora ao mesmo `TOOL_REGISTRY` gerando classes Python dinamicamente em
[`src/vulpcode/mcp/client.py`](https://github.com/vulpcode/vulpcode/tree/main/src/vulpcode/mcp/client.py):

```python
# src/vulpcode/mcp/client.py — esqueleto de _make_tool_adapter
def _make_tool_adapter(server_name: str, session: Any, mcp_tool: Any) -> type[Tool]:
    schema = getattr(mcp_tool, "inputSchema", None) or {"type": "object"}
    input_model = _input_model_from_schema(
        schema, name=f"{server_name}_{mcp_tool.name}_Input"
    )
    qualified_name = f"mcp__{server_name}__{mcp_tool.name}"
    description = (getattr(mcp_tool, "description", None) or "")[:500]

    @tool(
        name=qualified_name,
        description=description,
        requires_confirm=False,
    )
    class _Adapter(Tool):
        Input = input_model
        async def run(self, args: BaseModel) -> ToolResult:
            payload = args.model_dump()
            result = await session.call_tool(mcp_tool.name, payload)
            # ... extrai partes "text", checa isError ...
            return ToolResult(output=..., metadata={"server": server_name})

    return _Adapter
```

Pontos a notar:

- O **nome qualificado** e sempre `mcp__<servidor>__<tool>` — isso evita
  colisao com tools nativas (que tem nomes "limpos" como `Read`).
- O `Input` e gerado dinamicamente a partir do `inputSchema` declarado pelo
  servidor (JSON Schema -> classe Pydantic).
- A descricao e truncada em 500 caracteres para nao explodir o tamanho do
  prompt.
- Cada adapter MCP entra **no mesmo** `TOOL_REGISTRY`. Para o agent loop, nao
  ha diferenca entre uma tool nativa e uma MCP — ambas passam por
  `execute_tool_call`.

Quando um servidor e desconectado, `clear_mcp_tools()` (ou o shutdown geral)
remove os adapters do registry.

---

## 4. Helpers publicos

Reexportados em `vulpcode.tools` (ver [`tools/__init__.py`](https://github.com/vulpcode/vulpcode/tree/main/src/vulpcode/tools/__init__.py)):

```python
from vulpcode.tools import (
    TOOL_REGISTRY,        # dict[str, type[Tool]] — registry global
    Tool, ToolResult,     # ABCs
    tool,                 # decorator @tool(...)
    get_tool,             # lookup por nome (KeyError se nao existir)
    list_tools,           # list[type[Tool]] em ordem de registro
    clear_registry,       # esvazia o registry — SO em testes
    execute_tool_call,    # parse args + run + wrap erros em ToolResult
)
```

Resumo de uso:

| Funcao             | Quando usar                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| `TOOL_REGISTRY`    | leitura direta (debugging, introspecao)                                     |
| `get_tool(name)`   | obter a classe (e.g. para chamar `.to_schema()`)                            |
| `list_tools()`     | montar a lista de schemas para o provider                                   |
| `execute_tool_call(tc)` | despachar um `ToolCall` vindo do stream — ja faz validacao + wrap de erros |
| `clear_registry()` | apenas em tests com fixtures que precisam isolar tools                      |

A funcao [`execute_tool_call`][vulpcode.tools.base.execute_tool_call] e o que
o agent loop chama por baixo:

```python
# src/vulpcode/tools/base.py
async def execute_tool_call(tool_call, *, allow_unknown=False) -> ToolResult:
    if tool_call.name not in TOOL_REGISTRY:
        if allow_unknown:
            return ToolResult(error=f"Unknown tool: {tool_call.name}", is_error=True)
        raise KeyError(f"Unknown tool: {tool_call.name}")
    cls = TOOL_REGISTRY[tool_call.name]
    instance = cls()
    try:
        args = cls.parse_args(tool_call.arguments or {})
    except Exception as exc:
        return ToolResult(error=f"Invalid arguments: {exc}", is_error=True)
    try:
        return await instance.run(args)
    except Exception as exc:
        return ToolResult(error=f"{type(exc).__name__}: {exc}", is_error=True)
```

Tres caminhos de erro distintos viram `ToolResult(is_error=True)` em vez de
matarem o loop:

1. Tool desconhecida (com `allow_unknown=True`).
2. Argumentos invalidos (Pydantic `ValidationError`).
3. Excecao em `Tool.run`.

O modelo recebe a mensagem do erro como `role="tool"` no proximo turno e
costuma reagir corrigindo a chamada.

---

## 5. JSON Schema dos Inputs

[`Tool.to_schema`][vulpcode.tools.base.Tool.to_schema] devolve o formato
canonico que cada provider re-empacota
(ver [Provider translation](provider-translation.md#2-schema-de-tool-traducao-por-provider)):

```json
{
  "name": "Read",
  "description": "Read a file from the local filesystem.",
  "input_schema": {
    "type": "object",
    "properties": {
      "file_path": {
        "type": "string",
        "description": "Absolute path to the file."
      },
      "offset": { "type": "integer", "default": null },
      "limit":  { "type": "integer", "default": null }
    },
    "required": ["file_path"]
  }
}
```

O `input_schema` e produzido por `Input.model_json_schema()` da Pydantic v2 —
nao e escrito a mao. Para enriquecer descricoes de campo, use `Field(...)`:

```python
class Input(BaseModel):
    file_path: str = Field(description="Absolute path to the file.")
    offset: int | None = Field(default=None, description="0-indexed start line.")
    limit: int | None = Field(default=None, description="Max lines to read.")
```

A descricao do campo aparece na schema vista pelo modelo e influencia
fortemente quando/como ele decide chamar a tool.

---

## 6. Decisoes de design

- **Decorator-based (`@tool`)**: declarativo e o ponto de registro fica
  visivel ao lado da classe. Nao ha hooks magicos por subclassing — quem
  esquece o decorator simplesmente nao aparece em `list_tools()`, e o erro
  se manifesta na hora de chamar a tool, nao em build-time.
- **`TOOL_REGISTRY` global**: um unico dict por processo. Simples e
  suficiente — o Vulpcode roda um unico agent loop por processo CLI.
  Multi-instancia compartilharia o mesmo registry (o que torna isolamento
  por sessao mais complicado), mas hoje nao e um requisito.
- **`Input` aninhado obrigatorio**: forca cada tool a ter schema explicito
  (Pydantic), e a validacao roda **antes** de `run`. Tools nunca recebem
  argumentos invalidos — se chegou em `run`, e porque ja foi validado.
- **Imports explicitos no `__init__.py`**: descoberta automatica via
  walk-de-pacotes seria mais "magica" mas mais fragil (ordem de import,
  pacotes de terceiros). A lista explicita e a fonte de verdade e nao
  esconde dependencias.
- **MCP no mesmo registry**: nao ha "registry de MCP" separado. O agent loop
  trata native e MCP de forma uniforme; o prefixo `mcp__<server>__` e a
  unica forma de distinguir externamente.
- **Erros viram `ToolResult`**: errar nao para o agente — o erro vira
  contexto para o modelo, que pode tentar de novo. Excecoes inesperadas em
  `run` viram `ToolResult(is_error=True, error="<exc class>: <msg>")`.

---

## Veja tambem

- [Agent loop](agent-loop.md) — quem chama `execute_tool_call`.
- [Provider translation](provider-translation.md) — como o `input_schema` e
  re-empacotado por cada SDK.
- [API: Tools](../api/tools.md) — referencia formal de `Tool`, `ToolResult`
  e helpers.
- [Tools / Filesystem](../tools/filesystem.md), [Busca e Shell](../tools/search-and-shell.md),
  [Agente](../tools/agent.md), [Web](../tools/web.md) — guias de cada tool.
- [MCP](../mcp/index.md) — como conectar servidores e ver suas tools no
  registry.
