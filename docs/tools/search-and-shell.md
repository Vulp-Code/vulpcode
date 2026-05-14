# Busca e Shell

Quatro tools para procurar coisas e rodar processos:

| Tool         | Confirma? | Para que serve                                                  |
|--------------|-----------|-----------------------------------------------------------------|
| `Grep`       | nao       | Regex em arquivos, via ripgrep com fallback Python.             |
| `Bash`       | sim       | Roda `bash -c <cmd>` em foreground (com timeout) ou background. |
| `BashOutput` | nao       | Le incremental do output de um bash em background.              |
| `KillBash`   | sim       | Termina um processo bash em background.                         |

Source de verdade:
[`grep.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/grep.py),
[`bash.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/bash.py),
[`bash_background.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/bash_background.py),
[`_bash_registry.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/_bash_registry.py).

---

## Grep

**Categoria:** Busca  ·  **Confirma?** nao

Busca regex em arquivos. Se o binario `rg` estiver no `PATH`, usa
**ripgrep**; caso contrario cai em um fallback **Python** (`re` module)
que percorre arquivos com `pathlib.Path.rglob`.

### Schema de input

```python
from typing import Literal
from pydantic import BaseModel, Field


class Input(BaseModel):
    pattern: str
    path: str | None = None
    glob: str | None = None
    output_mode: Literal["content", "files_with_matches", "count"] = "content"
    flag_i: bool = Field(default=False, alias="-i")
    flag_A: int | None = Field(default=None, alias="-A")
    flag_B: int | None = Field(default=None, alias="-B")
    flag_C: int | None = Field(default=None, alias="-C")
    head_limit: int | None = None
    multiline: bool = False

    model_config = {"populate_by_name": True}
```

> Os flags `-i`, `-A`, `-B`, `-C` aceitam tanto o nome canonico (`flag_i`)
> quanto o alias com hifen (`-i`) — o LLM costuma passar o alias, codigo
> Python costuma usar o nome canonico.

### Comportamento

- `output_mode`:
    - `content` (default) — `caminho:linha:texto`.
    - `files_with_matches` — apenas paths.
    - `count` — `caminho:N` por arquivo com pelo menos uma ocorrencia.
- `path` default `.` (cwd).
- `glob` filtra arquivos (`-g` no `rg`; `Path.rglob(glob)` no fallback).
- `flag_i`: case-insensitive.
- `flag_C` (contexto antes+depois) tem prioridade sobre `-A`/`-B` no
  modo ripgrep.
- `multiline=True` ativa `-U --multiline-dotall` no rg, ou
  `re.DOTALL | re.MULTILINE` no Python.
- `head_limit` corta o output ao N primeiras linhas e adiciona
  `[truncated to N lines]`.
- Sem matches: retorna `output="No matches for {pattern!r}"` (nao e erro).

### ripgrep vs fallback Python

| Aspecto                     | ripgrep (`rg`)                          | Fallback Python                                |
|-----------------------------|-----------------------------------------|------------------------------------------------|
| Velocidade                  | rapido (paralelo, SIMD)                 | sequencial em Python puro                      |
| `.gitignore`                | respeitado por padrao                   | nao respeitado — varre tudo                    |
| Sintaxe regex               | Rust regex (semelhante a PCRE, sem look-around) | `re` do Python (look-around, named groups, etc) |
| `glob`                      | `-g <padrao>` (estilo `.gitignore`)     | `Path.rglob(<padrao>)` (estilo glob shell)     |
| Contexto (`-A` / `-B` / `-C`) | suportado                              | ignorado (so retorna a linha do match)         |
| `multiline`                 | `-U --multiline-dotall`                 | `re.DOTALL | re.MULTILINE`                     |
| `output_mode=count`         | `-c` por arquivo                        | conta manualmente                              |
| metadata                    | `{"backend": "ripgrep", ...}`           | `{"backend": "python", ...}`                   |

> Se voce precisa de comportamento determinista entre maquinas, instale
> ripgrep. Se nao quiser, o fallback funciona — mas perde features.

### Exemplo (no REPL)

```text
> procure "TODO" no diretorio src/, so nos .py
```

(O modelo chama `Grep({"pattern": "TODO", "path": "src/", "glob": "*.py"})`.)

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

GrepTool = get_tool("Grep")

# So nomes de arquivo
result = await GrepTool().run(
    GrepTool.Input(
        pattern=r"def \w+_async",
        path="src/",
        glob="*.py",
        output_mode="files_with_matches",
    )
)
print(result.output)
print(result.metadata)  # {"backend": "ripgrep" | "python", ...}

# Com flags via alias (jeito do LLM)
result = await GrepTool().run(
    GrepTool.Input.model_validate({
        "pattern": "error",
        "path": "/var/log",
        "-i": True,
        "-C": 2,
        "head_limit": 50,
    })
)
```

### Limitacoes

- O fallback Python **nao implementa contexto** (`-A`/`-B`/`-C`).
- Sem ripgrep, arvores grandes ficam lentas. Restrinja com `path` e `glob`.
- O regex passa por `rg` sem escape — caracteres especiais do shell ja sao
  protegidos porque usamos `create_subprocess_exec` (sem shell).

### Fonte

`src/vulpcode/tools/grep.py`

---

## Bash

**Categoria:** Shell  ·  **Confirma?** sim

Roda um comando shell via `bash -c "<command>"` usando
`asyncio.create_subprocess_exec`. Em foreground (default), espera ate
`timeout` ms e retorna stdout+stderr concatenados. Em background, registra o
processo no [bash registry](#bash-registry) e devolve um `bash_id` para uso
com [`BashOutput`](#bashoutput) e [`KillBash`](#killbash).

### Schema de input

```python
class Input(BaseModel):
    command: str
    timeout: int | None = None       # ms; default 120_000, max 600_000
    description: str | None = None   # cosmetico — ignorado pelo runtime
    run_in_background: bool = False
```

> `description` e um campo livre. O LLM costuma preencher com um resumo
> tipo `"build the project"` para se documentar; o runtime nao o usa.

### Comportamento

- Spawna `bash -c <command>` (sem `shell=True`, mas o bash interpreta o
  comando, entao expansoes `~`, `$VAR`, pipes, redirects, `&&` funcionam).
- `timeout` em milissegundos, default **120_000 (120 s)**, **clamp** em
  600_000 (10 min). Acima disso e silenciosamente reduzido para 600_000.
- Foreground:
    - Espera com `asyncio.wait_for` ate o timeout. Estourou? `proc.kill()`,
      `await proc.wait()`, retorna `is_error=True` com
      `error="Command timed out after Xs"` e `metadata["timeout"]=True`.
    - Output e `stdout + "\n" + stderr` (separador so se ambos existirem).
    - Se passar de **30 000 chars**, e truncado com sufixo
      `[truncated, full output N chars]`.
    - Exit code 0 → `is_error=False`, output preservado.
    - Exit code != 0 → `is_error=True`, mas o `output` ainda traz o que o
      processo imprimiu, e `metadata["exit_code"]` traz o codigo.
- Background:
    - `run_in_background=True` retorna **imediatamente** com
      `output="Started background process bash_xxxxxxxx: <command>"` e
      `metadata={"bash_id": "bash_xxxxxxxx", "background": True}`.
    - Stdout e stderr sao drenados em uma `asyncio.Task` para listas
      `bp.stdout` / `bp.stderr` no registry. Voce le com `BashOutput`.

### Exemplo (no REPL)

```text
> rode `pytest -q`
```

Em background:

```text
> rode `sleep 30 && echo done` em background
```

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

BashTool = get_tool("Bash")

# Foreground
result = await BashTool().run(
    BashTool.Input(command="echo $USER && uname -r", timeout=5_000)
)
print(result.output)
print(result.metadata)  # {"exit_code": 0, "command": "..."}

# Background
result = await BashTool().run(
    BashTool.Input(command="sleep 30 && echo done", run_in_background=True)
)
bash_id = result.metadata["bash_id"]  # "bash_abc12345"
```

### Limitacoes

- O timeout maximo de 600 s e duro — nao da pra subir. Para tarefas
  longas, use background.
- Output truncado em 30k chars no foreground. Para builds verbosos,
  redirecione para arquivo (`> /tmp/build.log 2>&1`) e leia com
  [`Read`](filesystem.md#read).
- Sem TTY: programas que esperam um terminal interativo (vim, less, prompts
  de senha) vao travar ou se comportar mal. Para senhas, use variaveis de
  ambiente ou ferramentas dedicadas.

### Fonte

`src/vulpcode/tools/bash.py`

---

## BashOutput

**Categoria:** Shell  ·  **Confirma?** nao

Le **incrementalmente** o output (stdout + stderr) de um processo iniciado
com `Bash(run_in_background=True)`. Cada chamada devolve **apenas as linhas
emitidas desde a chamada anterior** para aquele `bash_id` — um cursor
movel.

### Schema de input

```python
class Input(BaseModel):
    bash_id: str
    filter: str | None = None    # regex Python aplicado linha-a-linha
```

### Comportamento

- Erro (`is_error=True`) se o `bash_id` nao existe no registry — o erro
  inclui a lista atual de bash_ids ativos.
- `filter`: se passado, e compilado com `re.compile`. Linhas que **nao**
  casam o regex sao descartadas. Regex invalido vira erro
  `Invalid filter regex: ...`.
- Mantem dois cursores por processo: `stdout_offset` e `stderr_offset`.
  Linhas entre o offset e o fim do buffer sao retornadas e o offset avanca
  para o tamanho atual do buffer — chamadas futuras nao revisitam essas
  linhas.
- Status:
    - `running` se `exit_code is None` (drain ainda nao terminou).
    - `completed (exit code N)` se o processo ja terminou.
- Output e formatado com tags pseudo-XML:

  ```text
  <status>running</status>
  <stdout>
  linha 1 nova
  linha 2 nova
  </stdout>
  <stderr>
  warning: ...
  </stderr>
  ```

  Sem novas linhas e processo ainda rodando: `<no new output>`.

### Exemplo (fluxo bash background no REPL)

```text
> rode 'sleep 30 && echo done' em background
[Bash chamado com run_in_background=true; retorna bash_abc12345]

> /tools          # confirma que esta rodando

(depois de 30s)
> leia o output do bash bash_abc12345
[BashOutput retorna "done", status completed (exit code 0)]
```

### Exemplo (programatico)

```python
import asyncio
from vulpcode.tools import get_tool

BashTool = get_tool("Bash")
BashOutputTool = get_tool("BashOutput")

started = await BashTool().run(
    BashTool.Input(
        command="for i in 1 2 3; do echo hello $i; sleep 1; done",
        run_in_background=True,
    )
)
bash_id = started.metadata["bash_id"]

# Poll a cada 0.5s; cada chamada retorna so as linhas novas
for _ in range(10):
    out = await BashOutputTool().run(
        BashOutputTool.Input(bash_id=bash_id, filter=r"hello")
    )
    print(out.output)
    if not out.metadata["running"]:
        break
    await asyncio.sleep(0.5)
```

### Limitacoes

- Sem `tail` reverso — voce sempre ve so o "delta novo". Se quiser revisar
  uma linha antiga, ela ja saiu do alcance do cursor.
- O drain interno usa `readline()`, entao linhas extremamente longas (sem
  `\n`) ficam bufferizadas ate o `\n` chegar.

### Fonte

`src/vulpcode/tools/bash_background.py`

---

## KillBash

**Categoria:** Shell  ·  **Confirma?** sim

Termina um processo bash em background pelo `bash_id` e o remove do
registry.

### Schema de input

```python
class Input(BaseModel):
    bash_id: str
```

### Comportamento

- Erro se o `bash_id` nao existe (com lista dos ativos no erro).
- Se o processo **ja terminou**, o entry e removido do registry e retorna
  `Process bash_xxx already exited with code N` com
  `metadata["already_done"]=True`.
- Senao chama `bp.process.kill()` (SIGKILL no Linux), aguarda ate **5
  segundos** com `asyncio.wait_for(bp.process.wait(), 5.0)`. Se o processo
  ja foi embora ou o wait estourou, a excecao e silenciada.
- `exit_code` final = `bp.process.returncode` se nao for `None`, senao
  `-1` (sentinela "killed mas nao consegui ler o codigo").
- Remove sempre o entry do registry e retorna
  `output="Killed background process bash_xxx"`.

### Exemplo (no REPL)

```text
> mate o bash bash_abc12345
```

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

KillBashTool = get_tool("KillBash")
result = await KillBashTool().run(
    KillBashTool.Input(bash_id="bash_abc12345")
)
print(result.output)
print(result.metadata["exit_code"])  # -1 se foi morto a tiro
```

### Limitacoes

- `kill()` no asyncio = SIGKILL — sem chance do processo limpar (sem
  SIGTERM/SIGINT primeiro). Para shutdown gracioso, prefira mandar o sinal
  via `Bash` (`kill -INT <pid>`).
- Nao mata processos filhos automaticamente. Se o seu shell rodou
  `python -m http.server &`, o `kill` no bash pai pode deixar o filho
  orfao. Para isolar, rode com `setsid` ou `exec`.

### Fonte

`src/vulpcode/tools/bash_background.py`

---

## Bash registry

`Bash`, `BashOutput` e `KillBash` compartilham um registry global em
[`_bash_registry.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/_bash_registry.py).
Cada processo em background vira um `BackgroundProcess`:

```python
@dataclass
class BackgroundProcess:
    bash_id: str               # "bash_<8 hex>"
    command: str
    process: asyncio.subprocess.Process
    started_at: float
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)
    exit_code: int | None = None
    stdout_offset: int = 0     # cursor lido pelo BashOutput
    stderr_offset: int = 0
    _reader_task: asyncio.Task | None = None
```

E um modulo-singleton — um dict `_REGISTRY: dict[str, BackgroundProcess]`,
nao persistido em disco. Encerrou a sessao? Os processos somem (e podem
virar zumbis se voce nao matou). Em testes, use
`vulpcode.tools.base.clear_registry()` para o registry de tools, mas nao ha
helper publico para limpar o `_bash_registry` — manipule via
`KillBash` ou reinicie o processo.

---

## Veja tambem

- [Filesystem](filesystem.md) — `Read`, `Write`, `Edit`, `MultiEdit`, `Glob`.
- [Tools (visao geral)](index.md) — registry, modos de permissao.
- [Modos de permissao](../user-guide/permission-modes.md) — `default` /
  `auto` / `safe` / `plan` mudam o gating de `Bash` e `KillBash`.
