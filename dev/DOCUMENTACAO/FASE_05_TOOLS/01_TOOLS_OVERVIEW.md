# Tarefa 05.01 - Tools Overview

**Status**: PENDENTE
**Fase**: 05 - Tools
**Dependencias**: 04.04
**Bloqueia**: 05.02, 05.03

---

## Objetivo

Criar `tools/index.md` com visao geral das 14 tools nativas: tabela
classificada por categoria, links para detalhes, e explicacao de
`requires_confirm`.

---

## Arquivos a criar

- `docs/tools/index.md`

---

## Source de verdade

- `src/vulpcode/tools/*.py` — cada tool
- `src/vulpcode/tools/base.py` — `Tool`, `@tool`, `TOOL_REGISTRY`

---

## Estrutura

### 1. O que e uma tool?

Tools sao funcoes que o LLM pode invocar. Cada tool tem:
- Nome (`@tool(name=...)`)
- Descricao (`description`)
- Schema de input (`Input(BaseModel)`)
- Logica async (`run(args) -> ToolResult`)
- Flag `requires_confirm` (se sim, pede permissao antes de rodar)

O LLM ve apenas nome + descricao + schema. O resultado vai de volta como mensagem
`role="tool"` no historico.

### 2. Tabela de tools nativas

| Tool             | Categoria      | Confirma? | Funcao curta                            |
|------------------|----------------|-----------|------------------------------------------|
| `Read`           | Filesystem     | nao       | Le arquivo (cat -n)                      |
| `Write`          | Filesystem     | sim       | Cria/sobrescreve arquivo                 |
| `Edit`           | Filesystem     | sim       | Substitui string exata                   |
| `MultiEdit`      | Filesystem     | sim       | Multiplas edits atomicas                 |
| `Glob`           | Filesystem     | nao       | Match `**/*.py`, ordena por mtime        |
| `Grep`           | Busca          | nao       | Regex via ripgrep ou Python              |
| `Bash`           | Shell          | sim       | Executa comando shell                    |
| `BashOutput`     | Shell          | nao       | Le output incremental de bash em background |
| `KillBash`       | Shell          | sim       | Mata processo bash em background         |
| `WebFetch`       | Web            | nao       | Baixa URL e converte HTML->markdown      |
| `WebSearch`      | Web            | nao       | DuckDuckGo (default) ou Tavily           |
| `Task`           | Agente         | nao       | Lanca sub-agente com contexto isolado    |
| `TodoWrite`      | Agente         | nao       | Gerencia lista de TODOs da sessao        |
| `NotebookEdit`   | Agente         | sim       | Edita celulas .ipynb                     |

### 3. Categorias

- **Filesystem**: leitura/escrita de arquivos. [Detalhes →](filesystem.md) e
  [shell](shell.md) para Bash.
- **Busca**: `Grep` + `Glob`. [Detalhes →](search.md)
- **Shell**: `Bash`, `BashOutput`, `KillBash`. [Detalhes →](shell.md)
- **Web**: `WebFetch`, `WebSearch`. [Detalhes →](web.md)
- **Agente**: ferramentas de meta-orquestracao (`Task`, `TodoWrite`,
  `NotebookEdit`). [Detalhes →](agent.md)

### 4. Quais tools pedem confirmacao?

Tools com `requires_confirm=True`:
- Bash, Write, Edit, MultiEdit, KillBash, NotebookEdit

Em modo `default`, essas pedem `[y/a/n]`. Em modo `--auto`, todas passam.
Em `--safe`, ate as nao-destrutivas (Read, Glob, etc) pedem.

[Mais sobre permissoes →](../user-guide/permission-modes.md)

### 5. Como descobrir o que esta ativo

```
> /tools
```

Lista o registry atual. Inclui tools nativas + tools MCP carregadas (com
prefixo `mcp__<server>__<tool>`).

### 6. Adicionar tool customizada

Veja [Adicionando tool](../contributing/add-tool.md).

---

## Atualizar `mkdocs.yml`

Adicionar bloco `Tools`:

```yaml
nav:
  ...
  - Tools:
      - tools/index.md
      - Filesystem: tools/filesystem.md           # 05.02
      - Busca e Shell: tools/search-and-shell.md  # 05.02
      - Agente: tools/agent.md                    # 05.03
      - Web: tools/web.md                         # 05.03
```

---

## INSTRUCAO CRITICA

- Conferir a lista das 14 tools rodando `python -c "import vulpcode.tools;
  from vulpcode.tools import list_tools; [print(c._tool_name) for c in
  list_tools()]"`.
- Se a tabela divergir do `TOOL_REGISTRY`, ajustar.
- Para `requires_confirm`: grep `requires_confirm=True` em
  `src/vulpcode/tools/`.

---

## Etapas de Implementacao

### Etapa 1: Listar tools registradas
### Etapa 2: Criar `tools/index.md`
### Etapa 3: Atualizar `mkdocs.yml`
### Etapa 4: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/tools/index.md` criado
- [x] Tabela com 14 tools, categoria, requires_confirm, funcao curta
- [x] Lista de categorias com link para detalhes
- [x] Lista de tools que pedem confirmacao (verificada contra source)
- [x] Mencao a `/tools` slash command
- [x] `mkdocs.yml` atualizado com bloco `Tools`
- [x] `mkdocs build` continua passando

---

**End of Specification**
