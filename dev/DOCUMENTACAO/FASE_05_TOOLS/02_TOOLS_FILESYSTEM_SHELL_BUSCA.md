# Tarefa 05.02 - Tools Filesystem + Shell + Busca

**Status**: PENDENTE
**Fase**: 05 - Tools
**Dependencias**: 05.01
**Bloqueia**: 05.03

---

## Objetivo

Criar 2 paginas:
- `tools/filesystem.md` — Read, Write, Edit, MultiEdit, Glob
- `tools/search-and-shell.md` — Grep + Bash + BashOutput + KillBash

---

## Arquivos a criar

- `docs/tools/filesystem.md`
- `docs/tools/search-and-shell.md`

---

## Source de verdade

- `src/vulpcode/tools/read.py`, `write.py`, `edit.py`, `glob.py`, `grep.py`
- `src/vulpcode/tools/bash.py`, `bash_background.py`, `_bash_registry.py`

---

## Template para cada tool

````markdown
## <Nome>

**Categoria:** <cat>  ·  **Confirma?** <sim/nao>

<Descricao curta — 1-2 frases.>

### Schema de input

```python
class Input(BaseModel):
    file_path: str
    offset: int | None = None
    limit: int | None = None
```

### Comportamento

- ...
- ...

### Exemplo (no REPL)

```
> leia /etc/hostname
```

(O modelo chama internamente `Read({"file_path": "/etc/hostname"})`. Voce ve
um painel Rich com os args, depois o output.)

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

ReadTool = get_tool("Read")
result = await ReadTool().run(ReadTool.Input(file_path="/etc/hostname"))
print(result.output)
```

### Limitacoes

- ...

### Fonte

`src/vulpcode/tools/read.py`
````

---

## Conteudo de `filesystem.md`

5 secoes (uma por tool): Read, Write, Edit, MultiEdit, Glob.

Pontos importantes a cobrir em cada:

- **Read**: cat -n format, offset/limit, deteccao de binario, suporte a imagens
  (retorna metadata sem ler bytes).
- **Write**: cria diretorios pai, sobrescreve sem aviso, sempre UTF-8.
- **Edit**: `old_string` deve ser unico ou `replace_all=True`. Rejeita
  `old==new` e `old==""`.
- **MultiEdit**: aplica em memoria, escreve atomicamente. Falha => rollback.
- **Glob**: aceita padrao absoluto `/path/**/*.py` (graças ao fix), ordena
  por mtime decrescente, trunca a 100 resultados.

---

## Conteudo de `search-and-shell.md`

4 secoes: Grep, Bash, BashOutput, KillBash.

Pontos importantes:

- **Grep**:
  - Usa ripgrep (`rg`) se disponivel; cai para Python (`re` module) caso contrario
  - 3 modos: `content` (default), `files_with_matches`, `count`
  - Aliases `-i`, `-A`, `-B`, `-C`, `head_limit`, `multiline`
  - Tabela com diferenças entre rg e Python fallback
- **Bash**:
  - Roda via `bash -c`, async via `asyncio.subprocess`
  - Timeout default 120s, max 600s
  - `run_in_background=True` retorna `bash_id` para uso com BashOutput/KillBash
  - Output truncado a 30k chars
  - Exit code != 0 => `is_error=True` mas output ainda vem
- **BashOutput**:
  - Cursor incremental por `bash_id` (nao repete linhas ja lidas)
  - `filter` regex aplicado linha-a-linha
  - Status `running` ou `completed (exit code N)`
- **KillBash**:
  - Termina processo, espera ate 5s antes de marcar como -1
  - Remove do registry

Exemplo de fluxo bash background:

```
> rode 'sleep 30 && echo done' em background
[Bash chamado com run_in_background=true; retorna bash_abc12345]

> /tools  # ver que ainda esta rodando

(depois de 30s)
> leia o output do bash bash_abc12345
[BashOutput retorna "done", status completed]
```

---

## Atualizar `mkdocs.yml`

Atualizar nav (corrigir nomes dos arquivos):

```yaml
- Tools:
    - tools/index.md
    - Filesystem: tools/filesystem.md
    - Busca e Shell: tools/search-and-shell.md
    - Agente: tools/agent.md          # 05.03
    - Web: tools/web.md               # 05.03
```

---

## INSTRUCAO CRITICA

- O schema mostrado para cada tool deve ser o REAL — copiar do `Input` em
  cada arquivo source.
- Para `Edit`, mostrar o erro real quando `old_string` nao e unico.
- `Bash` tem `description` parametro — cosmetico, ignorado pelo runtime
  (mas o LLM usa para documentar a si mesmo).

---

## Etapas de Implementacao

### Etapa 1: Ler todos os tool sources
### Etapa 2: Criar `filesystem.md`
### Etapa 3: Criar `search-and-shell.md`
### Etapa 4: Atualizar `mkdocs.yml`
### Etapa 5: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/tools/filesystem.md` criado com 5 secoes (Read, Write, Edit, MultiEdit, Glob)
- [x] `docs/tools/search-and-shell.md` criado com 4 secoes (Grep, Bash, BashOutput, KillBash)
- [x] Cada secao tem: descricao, schema, comportamento, exemplo no REPL, exemplo programatico, fonte
- [x] Schemas batem com o `Input` real em cada arquivo source
- [x] `mkdocs.yml` atualizado
- [x] `mkdocs build` continua passando

---

**End of Specification**
