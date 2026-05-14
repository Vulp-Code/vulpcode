# Filesystem

As 5 tools desta categoria sao a forma como o LLM le e mexe em arquivos no
seu disco. Todas estao em
[`src/vulpcode/tools/`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/),
sao registradas em [`base.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/base.py)
via `@tool(...)`, e expostas para o modelo pela [`tools/index`](index.md).

| Tool        | Confirma? | Para que serve                                          |
|-------------|-----------|---------------------------------------------------------|
| `Read`      | nao       | Le arquivo de texto (com numeros de linha) ou imagem.    |
| `Write`     | sim       | Cria ou sobrescreve um arquivo (UTF-8).                  |
| `Edit`      | sim       | Substitui uma string exata em um arquivo.                |
| `MultiEdit` | sim       | Aplica varias substituicoes em um arquivo, atomicamente. |
| `Glob`      | nao       | Lista paths que casam um padrao, ordenados por mtime.    |

> Sobre confirmacao: tools com `requires_confirm=True` passam pelo
> `PermissionManager` antes de rodar. Veja
> [Modos de permissao](../user-guide/permission-modes.md).

---

## Read

**Categoria:** Filesystem  ·  **Confirma?** nao

Le um arquivo do disco e devolve o conteudo no formato `cat -n` (numero de
linha + tab + texto). Detecta arquivos binarios e imagens; para imagens
retorna apenas metadata, sem ler bytes.

### Schema de input

```python
class Input(BaseModel):
    file_path: str
    offset: int | None = None   # 1-based, default 1
    limit: int | None = None    # default 2000 linhas
```

### Comportamento

- Expande `~` (`Path.expanduser()`).
- Erro se o path nao existe ou e diretorio.
- **Imagens** (`.png .jpg .jpeg .gif .webp .bmp`) retornam
  `<image file: name, N bytes>` mais metadata `is_image=True` — bytes nao sao
  lidos.
- **Binarios**: amostra os primeiros 4096 bytes; se houver `\x00`, retorna
  erro `"File appears to be binary"`.
- Texto e lido como UTF-8 com `errors="replace"`.
- `offset` e 1-based (linha 1 e a primeira). Default = 1.
- `limit` default = 2000 linhas.
- Linhas com mais de **2000 chars** sao truncadas com sufixo
  `...[truncated]`.
- Se houver mais linhas alem de `offset+limit`, e adicionada uma cauda
  `[truncated: N more lines, use offset=K to continue]`.

### Exemplo (no REPL)

```text
> leia /etc/hostname
```

(O modelo chama internamente `Read({"file_path": "/etc/hostname"})`. Voce ve
um painel Rich com os args, depois o output em formato `cat -n`.)

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

ReadTool = get_tool("Read")
result = await ReadTool().run(
    ReadTool.Input(file_path="/etc/hostname")
)
print(result.output)
# 1\tmy-host
```

Lendo um trecho de um arquivo grande:

```python
result = await ReadTool().run(
    ReadTool.Input(
        file_path="/var/log/syslog",
        offset=1000,
        limit=200,
    )
)
```

### Limitacoes

- Nao decodifica imagens — devolve apenas o path e o tamanho. Quem usa o
  campo `metadata["image_path"]` e o adapter do provider (multi-modal).
- `errors="replace"` significa que bytes invalidos viram `�`; nao e
  fiel para encodings exoticos.
- Sem suporte nativo a streaming — arquivos enormes sao todos carregados em
  memoria antes do slice.

### Fonte

`src/vulpcode/tools/read.py`

---

## Write

**Categoria:** Filesystem  ·  **Confirma?** sim

Cria ou **sobrescreve** um arquivo com o conteudo dado. Cria diretorios pais
se necessario. Sempre grava UTF-8.

### Schema de input

```python
class Input(BaseModel):
    file_path: str
    content: str
```

### Comportamento

- Faz `Path(file_path).expanduser().resolve()` antes de gravar.
- `path.parent.mkdir(parents=True, exist_ok=True)` — diretorios pais sao
  criados sem aviso.
- **Sobrescreve sem aviso** se o arquivo ja existe.
- Codificacao fixa em UTF-8 (`encoding="utf-8"`).
- `OSError` (permissao, disco cheio, etc) vira `is_error=True` com
  `error="Failed to write {path}: ..."`.
- Em sucesso, `output = "Wrote {N} bytes to {path}"` e
  `metadata = {"file_path", "size", "created": True}`.

### Exemplo (no REPL)

```text
> crie /tmp/exemplo.txt com a frase "hello vulpcode"
```

(Como `Write` tem `requires_confirm=True`, o REPL pergunta
`Permitir Write? [y/a/n]` antes de gravar — a menos que voce esteja em
`--auto`.)

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

WriteTool = get_tool("Write")
result = await WriteTool().run(
    WriteTool.Input(
        file_path="/tmp/notas/dia1.md",  # /tmp/notas e criado se nao existir
        content="# Dia 1\n\n- vulpcode instalado\n",
    )
)
print(result.output)
# Wrote 32 bytes to /tmp/notas/dia1.md
```

### Limitacoes

- Sem `append` — sempre **rewrite** total.
- Sem checksum nem confirmacao de escrita parcial: erro durante o
  `write_text` deixa o arquivo possivelmente truncado.
- Nao preserva permissoes/owner do arquivo anterior.

### Fonte

`src/vulpcode/tools/write.py`

---

## Edit

**Categoria:** Filesystem  ·  **Confirma?** sim

Substitui uma ocorrencia exata de `old_string` por `new_string` em um
arquivo. Preserva o resto do arquivo intacto. Por seguranca, exige que
`old_string` seja **unica** — a menos que voce passe `replace_all=True`.

### Schema de input

```python
class Input(BaseModel):
    file_path: str
    old_string: str
    new_string: str
    replace_all: bool = False
```

### Comportamento

- Erro se o arquivo nao existe ou e diretorio.
- Le como UTF-8 (sem `errors="replace"` aqui — bytes invalidos = erro).
- Validacoes (todas viram `is_error=True` antes de qualquer escrita):

  | Caso                                | Mensagem de erro                                                                          |
  |-------------------------------------|-------------------------------------------------------------------------------------------|
  | `old_string == new_string`          | `old_string and new_string are identical`                                                 |
  | `old_string == ""`                  | `old_string cannot be empty`                                                              |
  | sem ocorrencias                     | `old_string not found`                                                                    |
  | mais de uma ocorrencia (`replace_all=False`) | `old_string is not unique (N occurrences). Add more context or set replace_all=True.` |

- Se passou nas validacoes, escreve o arquivo todo de volta em UTF-8.
- Output inclui um snippet numerado (3 linhas de contexto) ao redor da
  primeira mudanca.

### Exemplo (no REPL)

```text
> em /tmp/exemplo.txt, troque "hello" por "ola"
```

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

EditTool = get_tool("Edit")

# Caso simples — uma unica ocorrencia
result = await EditTool().run(
    EditTool.Input(
        file_path="/tmp/exemplo.txt",
        old_string="hello vulpcode",
        new_string="ola vulpcode",
    )
)

# Trocar todas as ocorrencias
result = await EditTool().run(
    EditTool.Input(
        file_path="/tmp/notas/dia1.md",
        old_string="TODO",
        new_string="DONE",
        replace_all=True,
    )
)
```

### Limitacoes

- A comparacao e **string-exata** (incluindo espacos e indentacao). Se
  voce copiou de uma saida `cat -n`, lembre-se de tirar o numero de linha
  e o tab.
- Nao e diff-aware: nao tenta resolver conflitos como o git faria.
- Sem multi-arquivo — para isso, chame varias vezes ou use
  [`MultiEdit`](#multiedit) (mesmo arquivo) ou um agente que orquestre.

### Fonte

`src/vulpcode/tools/edit.py`

---

## MultiEdit

**Categoria:** Filesystem  ·  **Confirma?** sim

Aplica varias substituicoes em um **mesmo** arquivo, sequencialmente, **em
memoria**. Se qualquer uma falhar, **nada** e gravado (rollback total).

### Schema de input

```python
class EditOp(BaseModel):
    old_string: str
    new_string: str
    replace_all: bool = False


class Input(BaseModel):
    file_path: str
    edits: list[EditOp]
```

### Comportamento

- `edits` vazio retorna erro `"edits list cannot be empty"`.
- Le o arquivo uma vez. Cada `EditOp` e aplicada **em cima do resultado da
  anterior** — voce pode encadear: editar, depois editar de novo o trecho
  recem-criado.
- Mesmas validacoes do `Edit`. Se a edit `#i` falha, o erro vira
  `Edit #i failed: <mensagem>` com `is_error=True` e o arquivo
  **fica intocado**.
- So depois de todas as N edits passarem o `path.write_text(...)` e chamado
  uma vez. Por isso o "atomicamente" — ou tudo ou nada.

### Exemplo (no REPL)

```text
> em /tmp/exemplo.py, troque "foo" por "bar" e "x = 1" por "x = 2"
```

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

MultiEditTool = get_tool("MultiEdit")
result = await MultiEditTool().run(
    MultiEditTool.Input(
        file_path="/tmp/exemplo.py",
        edits=[
            MultiEditTool.EditOp(old_string="foo", new_string="bar", replace_all=True),
            MultiEditTool.EditOp(old_string="x = 1", new_string="x = 2"),
        ],
    )
)
print(result.output)
# Applied 4 edit(s) across 2 operations to /tmp/exemplo.py
```

### Limitacoes

- Apenas **um arquivo** por chamada. Para edit cross-file, faca um loop ou
  delegue para um sub-agente via `Task` *(documentado na proxima fase)*.
- Como cada op opera no resultado da anterior, ordem importa: trocar
  `bar -> baz` depois de `foo -> bar` muda tambem os `bar` originais. Pense
  no efeito acumulado.
- Sem dry-run: para conferir antes, leia o arquivo, simule mentalmente, e
  mande.

### Fonte

`src/vulpcode/tools/edit.py`

---

## Glob

**Categoria:** Filesystem  ·  **Confirma?** nao

Lista arquivos que casam um padrao (`*`, `?`, `[abc]`, `**`). Aceita padrao
relativo (resolvido a partir de `path` ou cwd) ou **absoluto**. Resultados
ordenados por mtime decrescente, truncados a 100.

### Schema de input

```python
class Input(BaseModel):
    pattern: str
    path: str | None = None     # base; default = cwd
```

### Comportamento

- Se `pattern` e absoluto, e particionado em `(base, rel)`:
    - Com `**`: tudo antes do `**` vira a base, e o pattern relativo e
      `**` + sufixo. Ex.: `/home/x/**/*.py` → base `/home/x`, pattern `**/*.py`.
    - Sem `**`: a base e `Path(pattern).parent`, o pattern e o `name`.
- Se `path` e fornecido, ele tem prioridade como base; senao usa o anchor
  derivado do pattern absoluto, ou `Path.cwd()`.
- Erro se a base nao existe ou nao e diretorio.
- Filtra apenas arquivos (`p.is_file()`); diretorios sao ignorados.
- `OSError` ao chamar `stat()` em um match individual e silenciosamente
  pulado (links quebrados, permissao negada).
- Ordena por `st_mtime` desc, trunca a **100** resultados, e adiciona
  `[truncated to 100 most recent matches]` se sobraram.
- Sem matches retorna `output="No files match {pattern!r} under {base}"` com
  `is_error=False` (busca vazia nao e erro).

### Exemplo (no REPL)

```text
> liste todos os .py em src/
```

ou

```text
> me da os 10 .md mais recentes em /home/me/notes
```

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

GlobTool = get_tool("Glob")

# Padrao relativo + base explicita
result = await GlobTool().run(
    GlobTool.Input(pattern="**/*.py", path="src/vulpcode")
)

# Padrao absoluto (base inferida do pattern)
result = await GlobTool().run(
    GlobTool.Input(pattern="/home/me/projetos/**/*.md")
)
print(result.output)
```

### Limitacoes

- O **limite duro de 100** existe para nao saturar o contexto do modelo.
  Para listas maiores, refine o pattern ou use [`Bash`](search-and-shell.md#bash)
  com `find` / `fd`.
- Ordenacao por mtime e cara em arvores muito grandes — todo arquivo e
  `stat`-ado.
- Sem suporte a `.gitignore` (entra tudo, inclusive `node_modules` e
  `.venv`). Para respeitar `.gitignore`, prefira [`Grep`](search-and-shell.md#grep)
  com glob filter, que usa ripgrep.

### Fonte

`src/vulpcode/tools/glob.py`

---

## Veja tambem

- [Busca e Shell](search-and-shell.md) — `Grep`, `Bash`, `BashOutput`,
  `KillBash`.
- [Tools (visao geral)](index.md) — registry, categorias, modos de permissao.
- [Modos de permissao](../user-guide/permission-modes.md) — como `default`,
  `auto`, `safe` e `plan` mudam o gating de `Write`/`Edit`/`MultiEdit`.
