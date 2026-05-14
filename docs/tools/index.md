# Tools

As **tools** sao o vocabulario que o LLM usa para mexer no mundo real:
ler arquivos, rodar comandos, buscar na web, lancar sub-agentes. O Vulpcode
embarca **14 tools nativas**, e voce pode estender o conjunto via
[MCP](../user-guide/slash-commands.md) ou criando uma classe nova.

> Source de verdade:
> [`src/vulpcode/tools/`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/)
> e o registry global em
> [`src/vulpcode/tools/base.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/base.py).

---

## O que e uma tool?

Uma tool e uma classe que herda de `Tool` e e registrada no `TOOL_REGISTRY`
pelo decorator `@tool(...)`. Cada tool tem cinco coisas:

| Atributo            | De onde vem                  | Para que serve                                                |
|---------------------|------------------------------|----------------------------------------------------------------|
| Nome                | `@tool(name="...")`          | Identificador que o LLM chama (e que aparece em `/tools`).     |
| Descricao           | `@tool(description="...")`   | Texto que o LLM le para decidir quando usar a tool.            |
| Schema de input     | `class Input(BaseModel): ...`| Validado por Pydantic antes da execucao.                       |
| Logica              | `async def run(self, args)`  | Onde a coisa acontece. Retorna `ToolResult`.                   |
| `requires_confirm`  | `@tool(requires_confirm=...)`| Se `True`, passa pelo `PermissionManager` antes de rodar.      |

O LLM ve apenas **nome + descricao + schema**. Apos a execucao, o
`ToolResult` volta para o historico como uma mensagem `role="tool"` que o
modelo le no proximo turno.

```python
# Esqueleto minimo (similar ao que existe em src/vulpcode/tools/)
from pydantic import BaseModel
from vulpcode.tools.base import Tool, ToolResult, tool


@tool(
    name="Hello",
    description="Cumprimenta alguem pelo nome.",
    requires_confirm=False,
)
class HelloTool(Tool):
    class Input(BaseModel):
        name: str

    async def run(self, args: "HelloTool.Input") -> ToolResult:
        return ToolResult(output=f"Ola, {args.name}!")
```

---

## Tools nativas

As 14 tools registradas em `TOOL_REGISTRY`, em ordem de registro:

| Tool             | Categoria   | Confirma? | Funcao curta                                                   |
|------------------|-------------|-----------|----------------------------------------------------------------|
| `Read`           | Filesystem  | nao       | Le arquivo (formato `cat -n`), suporta `offset`/`limit`.       |
| `Write`          | Filesystem  | sim       | Cria/sobrescreve arquivo em UTF-8, cria diretorios pais.        |
| `Edit`           | Filesystem  | sim       | Substitui ocorrencia exata de `old_string` por `new_string`.    |
| `MultiEdit`      | Filesystem  | sim       | Aplica varias edits atomicamente em um arquivo.                 |
| `Glob`           | Filesystem  | nao       | Match de padroes (`**/*.py`), retorna paths ordenados por mtime.|
| `Grep`           | Busca       | nao       | Regex via ripgrep (com fallback Python), filtros por glob.      |
| `Bash`           | Shell       | sim       | Executa `bash -c`, foreground (com timeout) ou background.      |
| `BashOutput`     | Shell       | nao       | Le incrementalmente o output de um bash em background.          |
| `KillBash`       | Shell       | sim       | Termina um processo bash de background pelo `bash_id`.          |
| `WebFetch`       | Web         | nao       | Baixa URL, converte HTML para markdown.                         |
| `WebSearch`      | Web         | nao       | Busca DuckDuckGo (default) ou Tavily se `TAVILY_API_KEY`.       |
| `Task`           | Agente      | nao       | Lanca sub-agente com contexto isolado.                          |
| `TodoWrite`      | Agente      | nao       | Substitui a lista de TODOs da sessao.                           |
| `NotebookEdit`   | Agente      | sim       | Edita celulas de `.ipynb` (replace, insert, delete).            |

A lista canonica vem direto do codigo:

```bash
python -c "from vulpcode.tools import list_tools; \
    [print(c._tool_name) for c in list_tools()]"
```

---

## Categorias

- **Filesystem** — leitura/escrita e descoberta de arquivos: `Read`, `Write`,
  `Edit`, `MultiEdit`, `Glob`. [Detalhes →](filesystem.md)
- **Busca e Shell** — buscar por conteudo e rodar processos: `Grep`,
  `Bash`, `BashOutput`, `KillBash`. [Detalhes →](search-and-shell.md)
- **Web** — sair do localhost: `WebFetch`, `WebSearch`.
  *(documentado na proxima fase)*
- **Agente** — meta-orquestracao da sessao: `Task`, `TodoWrite`,
  `NotebookEdit`. *(documentado na proxima fase)*

---

## Quais tools pedem confirmacao?

Tools registradas com `requires_confirm=True`:

- `Bash`
- `Write`
- `Edit`
- `MultiEdit`
- `KillBash`
- `NotebookEdit`

Em modo `default`, antes de executar essas tools o vulpcode pergunta
`[y/a/n]` (sim / sempre nesta sessao / nao). Os outros modos mudam essa
politica:

| Modo        | Flag CLI   | Tools com `requires_confirm` | Tools nao-destrutivas |
|-------------|------------|------------------------------|------------------------|
| `default`   | (nenhuma)  | pede                         | rodam direto           |
| `auto`      | `--auto`   | rodam direto                 | rodam direto           |
| `safe`      | `--safe`   | pedem                        | tambem pedem           |
| `plan`      | `--plan`   | bloqueadas                   | bloqueadas             |

[Mais sobre permissoes →](../user-guide/permission-modes.md)

---

## Como descobrir o que esta ativo

Dentro do REPL:

```text
> /tools
```

Lista o registry atual, incluindo as nativas e qualquer tool MCP carregada
(que aparece com prefixo `mcp__<servidor>__<tool>`).

Por linha de comando:

```bash
python -c "from vulpcode.tools import list_tools; \
    [print(c._tool_name, '->', c._requires_confirm) for c in list_tools()]"
```

---

## Adicionar uma tool customizada

Voce pode registrar tools proprias decorando uma subclasse de `Tool` no
import-time. O passo-a-passo, com exemplo testavel, esta em
[Adicionando tool](../contributing/add-tool.md).

Para integrar tools de servidores externos (sem escrever Python),
veja [MCP](../user-guide/slash-commands.md#mcp).
