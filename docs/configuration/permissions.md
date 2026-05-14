# Permissoes (avancado)

Esta pagina trata o sistema de permissoes do ponto de vista de quem **estende
ou embute** o Vulpcode: como pre-aprovar tools no `config.toml`, como trocar o
prompter por uma logica customizada (Slack, web socket, log em disco), como
o spinner do REPL convive com o `stdin_prompter` e quais cuidados de
seguranca aplicar.

> Para a visao geral dos modos (`default`, `auto`, `safe`, `plan`), va para
> [Modos de permissao](../user-guide/permission-modes.md). Esta pagina **assume**
> esse conhecimento.

> Codigo de referencia: [`src/vulpcode/permissions.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/permissions.py),
> [`src/vulpcode/ui/streaming.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/streaming.py),
> [`src/vulpcode/app.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/app.py).

---

## Recap dos quatro modos

| Modo      | Flag      | Comportamento resumido                                                       |
|-----------|-----------|------------------------------------------------------------------------------|
| `default` | (sem)     | Tools com `requires_confirm=True` perguntam; resto roda direto.              |
| `auto`    | `--auto`  | Tudo aprovado sem perguntar. Allowlist e prompter sao ignorados.             |
| `safe`    | `--safe`  | Forca confirmacao em todas as tools, mesmo `Read`/`Glob`/`Grep`.             |
| `plan`    | `--plan`  | Nada executa. `PermissionDecision(allow=False, reason="plan mode")`.         |

A selecao do modo via CLI vive em
[`app.py` (`_make_permissions`)](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/app.py).
Os valores literais do enum `Mode` (`default`/`auto`/`safe`/`plan`) sao os
mesmos usados em config e em qualquer codigo que instancie um
`PermissionManager` diretamente.

Detalhes completos: [User Guide → Modos de permissao](../user-guide/permission-modes.md).

---

## Allowlist persistente: `always_allow_tools`

A unica chave de configuracao do bloco `[permissions]` e
`always_allow_tools`. Ela e copiada para o `_session_allowlist` no construtor
do `PermissionManager`:

```toml
# ~/.vulpcode/config.toml ou <projeto>/.vulpcode/config.toml
[permissions]
always_allow_tools = ["Read", "Glob", "Grep", "Bash"]
```

Cada nome listado e tratado **como se voce ja tivesse respondido `a`** para
aquela tool nesta sessao. A logica esta em
[`permissions.py:80-81`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/permissions.py#L80):

```python
if tool_call.name in self._session_allowlist:
    return PermissionDecision(True, False, "session allowlist")
```

Pontos a saber:

- Os nomes sao **case-sensitive** e devem bater com `_tool_name` da classe
  (`Read`, nao `read`).
- A allowlist nao e propagada entre sessoes — cada `vulp` reinicia o set a
  partir do `config.toml`.
- Em `--auto` ela e redundante. Em `--plan` ela nao tem efeito (o modo nega
  antes de checar a allowlist).
- Em `--safe` ela continua valendo: voce pode pre-aprovar leitura e ainda
  forcar confirmacao em escrita.

### Perfis de uso

| Perfil               | `always_allow_tools`                                          | Comentario                                                                         |
|----------------------|---------------------------------------------------------------|------------------------------------------------------------------------------------|
| **Dev local**        | `["Read", "Write", "Edit", "Bash", "Glob", "Grep"]`           | Voce confia no agente; quer fluxo continuo sem perder o `--plan`/`--safe` futuros. |
| **Dev cauteloso**    | `["Read", "Glob", "Grep"]`                                    | Leituras passam direto; escritas continuam pedindo `y`/`a`/`n`.                    |
| **Demo / observador**| `[]`                                                          | Allowlist vazia. Em `--safe`, cada acao espera resposta humana.                    |
| **CI / headless**    | (nao usar)                                                    | Use `--auto` em vez disso. Sem TTY, o prompter falha e a tool e negada.            |

---

## Customizar o prompter (uso programatico)

Quando voce embute o Vulpcode como **biblioteca** (bot Discord, web socket,
script que loga em disco), o `stdin_prompter` nao serve: nao ha terminal.
Substitua-o ao instanciar o `PermissionManager`.

### Assinatura

```python
from collections.abc import Awaitable, Callable

PrompterFn = Callable[[str, dict], Awaitable[str]]
```

O prompter recebe:

| Argumento | Tipo  | Conteudo                                                                            |
|-----------|-------|-------------------------------------------------------------------------------------|
| `message` | `str` | Texto pronto para exibir, ex.: `"Tool 'Bash' wants to run."`                        |
| `ctx`     | `dict`| `{"name": str, "arguments": dict}` — nome da tool e os args completos da chamada.   |

E **deve retornar** um destes tres caracteres:

| Retorno | Significado                                                                        |
|---------|------------------------------------------------------------------------------------|
| `"y"`   | aprova so esta chamada.                                                            |
| `"a"`   | aprova e adiciona a tool ao `_session_allowlist`.                                  |
| `"n"`   | rejeita; o agente recebe `ToolDeniedEvent`.                                        |

Qualquer outro valor (incluindo string vazia ou `None`) e tratado pelo
`stdin_prompter` como `"n"`. Se o prompter levanta excecao, o
`PermissionManager` retorna `PermissionDecision(allow=False, reason="prompt failed")`.

### Exemplo: prompter que aprova leitura e loga o resto

```python
import asyncio
from pathlib import Path
from vulpcode.permissions import Mode, PermissionManager

LOG = Path("/tmp/vulpcode-permissions.log")
SAFE_TOOLS = {"Read", "Glob", "Grep", "BashOutput"}

async def my_prompter(message: str, ctx: dict) -> str:
    name = ctx["name"]
    args = ctx["arguments"]
    with LOG.open("a") as fh:
        fh.write(f"{message} args={args}\n")
    # Aprova automaticamente leitura "passiva"
    if name in SAFE_TOOLS:
        return "a"
    # Para o resto, delega a um sistema externo (Slack, web socket, etc.)
    answer = await ask_human_via_slack(name, args)  # sua funcao
    return answer if answer in {"y", "a", "n"} else "n"

pm = PermissionManager(
    config={},          # ou o resultado de load_config()
    mode=Mode.DEFAULT,
    prompter=my_prompter,
)
```

### Exemplo: prompter sincrono adaptado

Se voce ja tem uma funcao bloqueante (`input()`, GUI, etc.), use
`asyncio.to_thread` para nao travar o loop:

```python
import asyncio

def ask_blocking(message: str, ctx: dict) -> str:
    print(message)
    return input("[y/a/n] > ").strip().lower()[:1] or "n"

async def my_prompter(message: str, ctx: dict) -> str:
    return await asyncio.to_thread(ask_blocking, message, ctx)
```

> Sempre normalize a resposta para `"y"`, `"a"` ou `"n"`. Caracteres
> diferentes nao causam excecao no `PermissionManager`, mas sao tratados como
> rejeicao silenciosa.

---

## Como o REPL integra com o prompter

O REPL nao usa o `stdin_prompter` diretamente. O `stream_agent_turn` em
[`ui/streaming.py:50-95`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/streaming.py#L50)
faz uma troca temporaria:

1. Le o `prompter` original do `agent.permissions`.
2. Substitui por um `_spinner_aware_prompter` que:
    1. **para o spinner do Rich** (`Live.stop()`),
    2. chama o prompter original (que escreve/le no stdin),
    3. **religa o spinner** (`Live.start()`) no `finally`.
3. No `finally` do turno, restaura o prompter original.

```python
async def _spinner_aware_prompter(msg: str, ctx: dict) -> str:
    stop_spinner()
    try:
        return await original_prompter(msg, ctx)
    finally:
        start_spinner("Thinking...")
```

Sem isso, `Rich.Live` rouba o stdout enquanto roda e a sua resposta digitada
fica sobreposta pelo spinner.

### Implicacoes para UIs custom

Se voce esta construindo uma UI nao-Rich (TUI propria, web, bot de chat),
**nao precisa** desse wrapper — o conflito so existe entre `stdin_prompter`
e `Live`. Em vez disso:

- Implemente um prompter que **ja seja assincrono** (`await asyncio.to_thread(input, ...)`)
  ou que **emita um evento** no seu sistema (web socket, fila, callback) e
  aguarde o retorno.
- Se voce usa progress bars proprios, pause/retome eles dentro do prompter,
  espelhando a logica do `_spinner_aware_prompter`.
- Em REPLs simples (sem spinner), basta passar `prompter=stdin_prompter`
  diretamente — ele ja usa `loop.run_in_executor` para nao bloquear o event
  loop.

---

## Boas praticas de seguranca

- **Producao / input nao confiavel**: nunca `Mode.AUTO`. Combine prompter
  customizado + `Mode.DEFAULT` ou `Mode.SAFE`. Lembre que em `--auto` o
  agente pode rodar `Bash`, `Write` e `Edit` em qualquer arquivo do sistema.
- **Dev local**: `always_allow_tools` so para tools que voce ja revisou.
  Mantenha `Bash` fora dessa lista quando o agente puder gerar comandos a
  partir de fontes externas (issues, e-mails, paginas web).
- **CI / headless**: use `--auto` deliberadamente, com prompt fixo, e
  isolando o ambiente (container descartavel, repositorio efemero). O
  `stdin_prompter` falha em CI sem TTY e a chamada e negada — nao confie
  nesse erro como protecao.
- **Auditoria**: combine seu prompter custom com persistencia em log. Cada
  decisao tambem aparece como evento — ver abaixo.
- **Hooks pre-permissao**: voce pode envolver o `Agent` numa subclasse e
  interceptar a tool call antes do `PermissionManager.check`, para
  bloquear paths, validar args ou aplicar regras de policy. A logica do loop
  vive em `Agent.turn` (`src/vulpcode/agent.py`).
- **Logging / observabilidade**: tools chamadas, finalizadas e negadas
  emergem como `ToolStartEvent`, `ToolEndEvent` e `ToolDeniedEvent` no
  stream do `Agent.turn(...)`. Ligar uma sink externa e direto: itere o
  generator e despache os eventos para sua plataforma de observabilidade.

```python
from vulpcode.agent import ToolStartEvent, ToolDeniedEvent

async for ev in agent.turn(user_input):
    if isinstance(ev, ToolStartEvent):
        log_to_metrics("tool_start", ev.tool_call.name, ev.tool_call.arguments)
    elif isinstance(ev, ToolDeniedEvent):
        log_to_metrics("tool_denied", ev.tool_call.name, ev.reason)
```

---

## Referencia: tools nativas e `requires_confirm`

A flag e setada no decorator `@tool(...)` de cada arquivo em
`src/vulpcode/tools/`. Verificavel a qualquer momento com:

```bash
grep -rn "requires_confirm=" src/vulpcode/tools/
```

### Tools com `requires_confirm=True`

Pedem confirmacao no modo `default` (e em `safe` para qualquer outra). Em
`auto` rodam direto.

| Tool           | Arquivo                         | Por que pede confirmacao                  |
|----------------|---------------------------------|--------------------------------------------|
| `Bash`         | `tools/bash.py`                 | executa shell arbitrario via `bash -c`.    |
| `KillBash`     | `tools/bash_background.py`      | termina processo background gerenciado.    |
| `Write`        | `tools/write.py`                | cria ou sobrescreve arquivo no disco.      |
| `Edit`         | `tools/edit.py`                 | substitui texto em arquivo existente.      |
| `MultiEdit`    | `tools/edit.py`                 | aplica varias edicoes atomicamente.        |
| `NotebookEdit` | `tools/notebook.py`             | modifica celulas de `.ipynb`.              |

### Tools com `requires_confirm=False`

Rodam direto em `default` e `auto`. Em `safe` ainda pedem confirmacao
(porque o modo forca `requires=True` para qualquer tool).

| Tool         | Arquivo                       | Comentario                                    |
|--------------|-------------------------------|-----------------------------------------------|
| `Read`       | `tools/read.py`               | leitura de arquivo, sem efeito colateral.     |
| `Glob`       | `tools/glob.py`               | busca por padrao de path.                     |
| `Grep`       | `tools/grep.py`               | busca por conteudo (ripgrep).                 |
| `BashOutput` | `tools/bash_background.py`    | apenas le saida de processo ja em execucao.   |
| `WebFetch`   | `tools/web.py`                | GET HTTP — efeito de rede, nao de disco.      |
| `WebSearch`  | `tools/web.py`                | consulta motor de busca.                      |
| `Task`       | `tools/task.py`               | despacha sub-agente; ele tem seu proprio PM.  |
| `TodoWrite`  | `tools/todo.py`               | edita o todo-list em memoria do turno.        |

Sub-agentes via `Task` herdam o `PermissionManager` do agente raiz. Quem
roda em `--safe` no agente raiz tambem ve os prompts disparados pelo
sub-agente.

---

## Veja tambem

- [Modos de permissao](../user-guide/permission-modes.md) — visao geral dos
  quatro modos com tabela CLI.
- [Tools](../tools/index.md) — descricao de cada tool nativa, seus args e
  retornos.
- [config.toml](config-toml.md) — referencia completa de chaves; `[permissions]`
  e o bloco que abriga `always_allow_tools`.
- Codigo: [`permissions.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/permissions.py),
  [`ui/streaming.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/ui/streaming.py).
