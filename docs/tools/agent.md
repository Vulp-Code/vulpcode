# Agente

Tres tools de meta-orquestracao — coisas que mexem na propria conduta da
sessao em vez de no filesystem ou no shell:

| Tool           | Confirma? | Para que serve                                                 |
|----------------|-----------|-----------------------------------------------------------------|
| `Task`         | nao       | Lanca um sub-agente com contexto isolado.                       |
| `TodoWrite`    | nao       | Substitui a lista de TODOs da sessao (em memoria do processo). |
| `NotebookEdit` | sim       | Edita celulas de Jupyter `.ipynb` (replace / insert / delete). |

Source de verdade:
[`task.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/task.py),
[`todo.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/todo.py),
[`notebook.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/notebook.py).

---

## Task

**Categoria:** Agente  ·  **Confirma?** nao

Lanca um **sub-agente** — um `Agent` totalmente novo, com sua propria
sequencia de mensagens — para tratar um pedaco de trabalho com contexto
isolado. O sub-agente roda ate o fim (sem turnos do usuario no meio) e
devolve o texto final como output da tool.

> **Nao e gratis.** Cada `Task` faz **outra chamada de API completa** para o
> provider (uma sessao inteira: prompt do sistema + sua tarefa + cada turno
> de tool calling). O custo aparece como tokens normais na sua fatura. Use
> com cabeca: tarefas pequenas o orquestrador faz mais barato sozinho.

### Schema de input

```python
from typing import Literal
from pydantic import BaseModel


class Input(BaseModel):
    description: str                                            # rotulo curto
    prompt: str                                                 # tarefa do sub-agente
    subagent_type: Literal["general-purpose", "Explore"] = "general-purpose"
```

### subagent_type e ALLOWED_TOOLS

O `subagent_type` controla **dois** comportamentos: o system prompt
embutido e o subset de tools que o sub-agente enxerga. Os dois mapas vivem
em `task.py` (`SUBAGENT_PROMPTS` e `ALLOWED_TOOLS`):

| `subagent_type`    | System prompt resumido                              | Tools permitidas                                                                         |
|--------------------|------------------------------------------------------|------------------------------------------------------------------------------------------|
| `general-purpose`  | Resolva a tarefa em poucos passos. Use tools livremente. Termine com a resposta em texto puro. | `Read`, `Write`, `Edit`, `MultiEdit`, `Bash`, `BashOutput`, `Grep`, `Glob`, `WebFetch`, `WebSearch`, `TodoWrite` |
| `Explore`          | So leitura — encontre arquivos e padroes. Nao edite, nao rode shell alem de `find`/`grep`. | `Read`, `Grep`, `Glob`                                                                   |

**Observacoes importantes:**

- **Sem recursao.** Mesmo dentro de `general-purpose`, o `Task` e
  filtrado fora da lista. Um sub-agente nao pode chamar outro sub-agente
  na v1.
- **Provider e modelo herdados** da config principal — o vulpcode chama
  `load_config()` (lazy import, dentro de `run`) e usa
  `default_provider` + `default_model`. Nao da pra mandar o sub-agente
  rodar em outro modelo.
- **Tools MCP nao sao herdadas.** O sub-agente so ve as tools nativas
  permitidas, nao as carregadas via MCP na sessao principal.
- **Confirmacoes valem dentro do sub-agente.** Se o `general-purpose`
  resolve chamar `Bash`, ainda passa pelo `PermissionManager` da
  configuracao do processo.

### Quando usar (e quando nao)

Bom para:

- **Pesquisas paralelas** — varias `Task` independentes em uma resposta
  exploram caminhos sem inflar o contexto principal.
- **Tarefas auto-contidas** que nao precisam do historico (ex.: "leia
  esse arquivo e me diga se tem `TODO`").
- **Evitar poluicao** — output massivo (logs, AST, dump de arquivo grande)
  fica na transcript do sub-agente, e voce so recebe a conclusao.

Pesa contra:

- Tarefas curtas (`Read` direto e mais barato).
- Trabalho que precisa do historico atual (o sub-agente comeca em zero).
- Loops que dependem de feedback humano (sub-agente nao tem turnos do
  usuario).

### Erros e fallback

Se algo der errado **antes** do sub-agente comecar — falha ao carregar
config, build do provider, ou init do `Agent` — a tool retorna
`is_error=True` com mensagem `Subagent unavailable (...): <motivo>`. Se a
falha acontece **durante** a execucao, o erro e
`Subagent failed: <Tipo>: <mensagem>`. Em ambos os casos a sessao
principal segue normalmente.

### Exemplo (no REPL)

```text
> use a tool Task com subagent_type="Explore" e prompt
  "encontre todos os arquivos de teste que mencionam 'subprocess'"
```

(O modelo chama
`Task({"description": "find subprocess usage", "prompt": "...", "subagent_type": "Explore"})`,
o sub-agente faz `Grep`/`Glob` e devolve a lista.)

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

TaskTool = get_tool("Task")

result = await TaskTool().run(
    TaskTool.Input(
        description="audit imports",
        prompt="Liste todos os modulos que importam 'requests' em src/.",
        subagent_type="Explore",
    )
)
print(result.output)
print(result.metadata)  # {"subagent_type": "Explore", "description": "..."}
```

### Fonte

`src/vulpcode/tools/task.py`

---

## TodoWrite

**Categoria:** Agente  ·  **Confirma?** nao

Mantem uma **lista de TODOs em memoria** que o LLM usa para se planejar em
tarefas multi-step. Cada chamada **substitui a lista inteira** — paridade
com o comportamento do Claude Code: o modelo pega o estado atual, ajusta,
e reescreve. Sem patch incremental.

### Schema de input

```python
from typing import Literal
from pydantic import BaseModel, Field


class TodoItem(BaseModel):
    content: str                                          # imperativo: "Run tests"
    activeForm: str                                       # gerundio: "Running tests"
    status: Literal["pending", "in_progress", "completed"]


class Input(BaseModel):
    todos: list[TodoItem] = Field(default_factory=list)
```

### Validacao: no maximo 1 in_progress

O `field_validator` em `TodoWriteTool.Input` recusa qualquer chamada com
**dois ou mais itens** em `in_progress` simultaneamente:

```text
ValueError: at most one task may be 'in_progress' at a time
```

A regra existe para dar um sinal claro de "estou trabalhando nisso agora"
— se o LLM tentar marcar varias coisas como ativas, a chamada falha e ele
e forcado a corrigir. Zero `in_progress` e permitido (lista toda
`pending` ou `completed`).

### Comportamento

- Armazenamento: dict modulo-global em `todo.py`
  (`_TODO_STORE: dict[str, list[TodoItem]]`), chaveado por session id.
  Hoje so existe a sessao `"default"`. **Nao persiste em disco** —
  encerrou o processo, sumiu.
- Substituicao **completa** a cada chamada — `_TODO_STORE[...] = list(args.todos)`.
- Output renderizado e uma lista numerada com markers no estilo task list:

  ```text
  1. [~] Running tests
  2. [ ] Pending Y
  3. [x] Done Z
  ```

  - `[~]` = `in_progress` — usa o `activeForm` (gerundio).
  - `[ ]` = `pending` — usa o `content`.
  - `[x]` = `completed` — usa o `content`.

- Lista vazia retorna `<empty list>` (nao e erro).
- `metadata`: `{"session": "default", "total": N, "in_progress": k, "completed": m}`.

### Quando o LLM usa

O modelo costuma chamar TodoWrite **quando a tarefa tem 3+ passos
distintos** — refactors espalhados, debug com varias hipoteses, qualquer
coisa em que ele precise se organizar. No REPL, voce vai ver um painel
Rich da TodoWrite atualizando entre os turnos: e ele declarando o plano
para si mesmo. Tarefa simples (pergunta direta, edicao pontual) nao
dispara TodoWrite.

### Helpers para inspecao

```python
from vulpcode.tools.todo import get_todos, clear_todos

# Snapshot da lista atual (copia)
items = get_todos()             # session_id default = "default"
for t in items:
    print(t.status, t.content)

# Apaga a lista da sessao
clear_todos()
```

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool
from vulpcode.tools.todo import TodoItem

TodoWriteTool = get_tool("TodoWrite")

result = await TodoWriteTool().run(
    TodoWriteTool.Input(
        todos=[
            TodoItem(
                content="Read failing test",
                activeForm="Reading failing test",
                status="completed",
            ),
            TodoItem(
                content="Patch parser",
                activeForm="Patching parser",
                status="in_progress",
            ),
            TodoItem(
                content="Re-run pytest -k parser",
                activeForm="Re-running pytest -k parser",
                status="pending",
            ),
        ]
    )
)
print(result.output)
# 1. [x] Read failing test
# 2. [~] Patching parser
# 3. [ ] Re-run pytest -k parser
```

### Fonte

`src/vulpcode/tools/todo.py`

---

## NotebookEdit

**Categoria:** Agente  ·  **Confirma?** sim

Edita celulas de um notebook Jupyter (`.ipynb`) operando direto no JSON.
Tres modos: `replace` (default), `insert`, `delete`. A celula alvo e
localizada por **id** ou por **numero** (0-based).

### Schema de input

```python
from typing import Literal
from pydantic import BaseModel


class Input(BaseModel):
    notebook_path: str
    new_source: str = ""
    cell_id: str | None = None
    cell_number: int | None = None
    cell_type: Literal["code", "markdown"] | None = None
    edit_mode: Literal["replace", "insert", "delete"] = "replace"
```

`replace` e `delete` exigem **um dos dois localizadores** (`cell_id` ou
`cell_number`); a falta de ambos vira `ValueError` na validacao Pydantic.
`insert` aceita ambos vazios — nesse caso a celula e anexada ao **fim**.

### Os tres modos

| Modo      | O que faz                                              | `new_source` | `cell_type`                  | Localizador                                |
|-----------|---------------------------------------------------------|--------------|------------------------------|--------------------------------------------|
| `replace` | Substitui o `source` da celula existente.              | usado        | opcional — troca o tipo se passado (limpa `outputs`/`execution_count` ao virar markdown) | obrigatorio |
| `insert`  | Cria celula nova e insere no indice (ou no fim).       | usado        | opcional, default `code`     | opcional — sem ele, anexa no fim           |
| `delete`  | Remove a celula localizada.                             | ignorado     | ignorado                     | obrigatorio                                |

Detalhes do `replace`:

- O `source` e quebrado em **lista de strings** com `\n` mantido (via
  `str.splitlines(keepends=True)`) — formato canonico do `.ipynb`.
- Se `cell_type` for passado, o `cell_type` da celula e atualizado. Ao
  virar `markdown`, `outputs` e `execution_count` sao removidos (eles nao
  fazem sentido em markdown e a maioria dos viewers reclama se sobrarem).

Detalhes do `insert`:

- Cria a celula com um `id` novo (`uuid.uuid4()` truncado em 8 chars),
  `metadata: {}`, `source` quebrado em lista. Se for `code`, ja sai com
  `outputs: []` e `execution_count: None`.
- Posicao: se voce passa um localizador, a celula entra **antes** dele
  (mesmo indice); sem localizador, anexa no fim.

Detalhes do `delete`:

- Pop pelo indice. `metadata` retorna o `cell_id` removido e
  `removed_index`.

### Preservacao do notebook

- Lido com `json.load` UTF-8, escrito com `json.dump(..., indent=1, ensure_ascii=False)`
  e termina com newline — formato proximo do que o Jupyter escreve.
- `nbformat`, `nbformat_minor`, `metadata`, `cells[*].metadata`, `cells[*].id`
  e demais chaves nao tocadas sao **preservadas** — a tool nao reescreve o
  notebook, so opera nos campos relevantes.
- Cada chamada e uma reescrita do arquivo inteiro. Notebooks gigantes
  (10k+ celulas) pagam o custo do roundtrip JSON, mas em tamanhos normais
  (algumas centenas) e barato.

### Erros tipicos

- `Notebook does not exist: <path>` — caminho ruim.
- `Cannot parse notebook: <exc>` — `.ipynb` corrompido ou nao-JSON.
- `Notebook has no 'cells' key` — arquivo nao tem o campo `cells`.
- `Cell not found by id or number` — em `replace`/`delete`, o localizador
  nao casou nada.

### Exemplo (no REPL)

```text
> use a tool NotebookEdit para substituir a celula 3 do notebook
  /tmp/analise.ipynb por "df = pd.read_csv('novo.csv')"
```

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

NotebookEditTool = get_tool("NotebookEdit")

# 1) Substitui pelo numero
result = await NotebookEditTool().run(
    NotebookEditTool.Input(
        notebook_path="/tmp/analise.ipynb",
        cell_number=3,
        new_source="df = pd.read_csv('novo.csv')\ndf.head()",
    )
)
print(result.output)  # "Notebook /tmp/analise.ipynb updated (replace)"

# 2) Insere uma celula markdown logo antes da celula 0 (vai para o topo)
result = await NotebookEditTool().run(
    NotebookEditTool.Input(
        notebook_path="/tmp/analise.ipynb",
        cell_number=0,
        cell_type="markdown",
        edit_mode="insert",
        new_source="# Analise de vendas\nDados de Q4 2026.",
    )
)

# 3) Deleta pelo id
result = await NotebookEditTool().run(
    NotebookEditTool.Input(
        notebook_path="/tmp/analise.ipynb",
        cell_id="ab12cd34",
        edit_mode="delete",
    )
)
```

### Fonte

`src/vulpcode/tools/notebook.py`

---

## Veja tambem

- [Filesystem](filesystem.md) — `Read`, `Write`, `Edit`, `MultiEdit`,
  `Glob`. As edits do `NotebookEdit` complementam: para um `.py` use
  `Edit`; para um `.ipynb`, use `NotebookEdit`.
- [Busca e Shell](search-and-shell.md) — tools que sub-agentes
  `general-purpose` herdam.
- [Web](web.md) — `WebFetch` / `WebSearch`, tambem disponiveis para
  sub-agentes `general-purpose`.
- [Modos de permissao](../user-guide/permission-modes.md) — afetam
  `NotebookEdit` (que requer confirmacao) e cascateiam para o
  sub-agente do `Task`.
