# Tarefa 07.01 — Documentação: README + mkdocs + `vulp providers`

**Status**: PENDENTE
**Fase**: 07 - Docs
**Dependências**: FASE_01 a FASE_06 concluídas
**Bloqueia**: nada (último passo)

---

## Objetivo

Refletir as adições nesta fase em:

1. **README.md**: nova linha na tabela de providers, exemplo de uso.
2. **`docs/`** (mkdocs): página nova `docs/providers/internal-llm-agentic.md` + página
   `docs/tools/validated-write.md` documentando a família `Write*` especializada.
3. **`vulp providers`** (CLI): confirmar que mostra o nome novo.
4. **CHANGELOG.md**: entrada da próxima versão.

---

## README.md

### Atualizar tabela "Supported providers" (linha ~120)

Adicionar imediatamente abaixo de `internal-llm`:

```markdown
| `internal-llm-agentic` | Corporate endpoint (text-protocol tool calling) | x | | |
```

A coluna `Tools` ganha `x` para refletir o protocolo de texto.

### Atualizar seção "Use an internal corporate endpoint"

Substituir o exemplo atual por dois exemplos lado-a-lado:

```markdown
### Use an internal corporate endpoint

The library ships two providers for internal corporate `/chatCompletion` endpoints:

| Provider | When to use |
|---|---|
| `internal-llm` | Plain chat only — no file creation, no shell, no agentic loop |
| `internal-llm-agentic` | Full agentic flow via a text-based tool protocol (recommended) |

Both read the same env vars:

```bash
export INTERNAL_LLM_ENDPOINT="https://internal.example.com/v1/chat"
export INTERNAL_LLM_USER_UUID="00000000-0000-0000-0000-000000000000"

# Chat-only mode
vulp --provider internal-llm

# Full agent (creates files, runs validators, retries on syntax errors)
vulp --provider internal-llm-agentic
```
```

---

## mkdocs

### `docs/providers/internal-llm-agentic.md` (NEW)

Estrutura (preenchimento real fica para o agente implementador):

1. Overview — por que existe, diferença para `internal-llm`.
2. Configuration — envs e bloco `[providers.internal-llm-agentic]` do `config.toml`.
3. The text protocol — descrever `<vulp:tool>`, `<vulp:arg>`, `<vulp:content>`,
   `<vulp:tool_result>`. Apontar para o source em `_text_tool_protocol.py`.
4. Repair loop — exemplo passo-a-passo do que acontece quando o modelo gera um
   `.py` com `SyntaxError`.
5. Caveats — limites: sem streaming, sem visão, depende do modelo seguir o protocolo,
   max_iters elevado para 50.
6. Troubleshooting — sintomas comuns (modelo emite prosa entre tags, `<vulp:content>`
   contém `</vulp:content>` literal, etc.).

### `docs/tools/validated-write.md` (NEW)

Estrutura:

1. Why a family — diferença para a `Write` genérica.
2. Common contract — todas validam antes de gravar; todas usam atomic save.
3. Tabela exaustiva:

```markdown
| Tool | File type | Validator | Optional dep |
|---|---|---|---|
| WritePy | .py | ast.parse | — |
| WriteIpynb | .ipynb | nbformat.validate + per-cell ast.parse | nbformat |
| WriteMd | .md | markdown-it + balanced fences | markdown-it-py |
| WriteDocx | .docx | round-trip via python-docx | python-docx |
| WritePdf | .pdf | round-trip via pypdf | weasyprint OR reportlab + pypdf |
| WriteJson | .json | json.loads | — |
| WriteYaml | .yaml/.yml | yaml.safe_load | PyYAML |
| WriteToml | .toml | tomllib.loads | — |
| WriteCsv | .csv | csv.reader + column-count check | — |
| WriteXml | .xml | ET.fromstring | — |
| WriteHtml | .html | html.parser (lenient) / lxml (strict) | lxml (strict) |
| WriteSh | .sh | bash -n | — (bash runtime) |
| WriteSql | .sql | sqlparse + parens/quote balance | sqlparse |
| WriteSvg | .svg | XML parse + root tag check | — |
| WriteDot | .dot | pydot parse | pydot |
```

4. Atomic save — explicar tmp + rename, sem residuals.
5. Como funciona o auto-reparo — referência para `docs/providers/internal-llm-agentic.md`.

### `mkdocs.yml`

Adicionar as duas páginas novas no `nav:`:

```yaml
nav:
  - Home: index.md
  - Providers:
    - ...
    - Internal LLM (agentic): providers/internal-llm-agentic.md
  - Tools:
    - ...
    - Validated Write family: tools/validated-write.md
```

---

## `vulp providers` (CLI)

Verificar em `src/vulpcode/commands/` (ou onde estiver a impl de `providers`) que a
listagem usa `list_provider_names()` do registry. Se sim, nenhuma mudança necessária —
o nome novo aparece automaticamente. Caso contrário, adicionar.

Smoke:

```bash
vulp providers | grep internal-llm-agentic
```

---

## CHANGELOG.md

Adicionar entrada no topo:

```markdown
## [Unreleased]

### Added
- New provider `internal-llm-agentic`: corporate `/chatCompletion` endpoints
  now get full agentic capabilities via a text-based tool calling protocol.
- New family of file-creation tools with built-in validation and atomic save:
  `WritePy`, `WriteIpynb`, `WriteMd`, `WriteDocx`, `WritePdf`, `WriteJson`,
  `WriteYaml`, `WriteToml`, `WriteCsv`, `WriteXml`, `WriteHtml`, `WriteSh`,
  `WriteSql`, `WriteSvg`, `WriteDot`.
- New optional extra `[docs-tools]` for the non-stdlib validators.

### Changed
- `Agent` accepts a new `max_iters` parameter; default remains 25 but
  `internal-llm-agentic` uses 50 to accommodate repair iterations.
```

---

## Etapas

### Etapa 1 — Editar `README.md`

Tabela + seção de uso.

### Etapa 2 — Criar `docs/providers/internal-llm-agentic.md`

### Etapa 3 — Criar `docs/tools/validated-write.md`

### Etapa 4 — Atualizar `mkdocs.yml`

### Etapa 5 — Atualizar `CHANGELOG.md`

### Etapa 6 — Build docs local

```bash
pip install -e ".[docs]"
mkdocs build --strict
```

`--strict` falha em link quebrado / página fora do nav. Resolver antes de fechar.

### Etapa 7 — Smoke `vulp providers`

```bash
vulp providers | grep internal-llm-agentic
```

---

## Critérios de Aceite

- [x] README.md tabela inclui `internal-llm-agentic`
- [x] README.md seção corporate endpoint mostra ambos os modos
- [x] `docs/providers/internal-llm-agentic.md` existe e cobre os 6 sub-tópicos
- [x] `docs/tools/validated-write.md` existe com a tabela de 15 tools
- [x] `mkdocs build --strict` passa sem warning
- [x] `vulp providers` lista o nome novo
- [x] `CHANGELOG.md` tem entrada `[Unreleased]`

---

## Riscos

| Risco | Probabilidade | Mitigação |
|-------|---------------|-----------|
| `mkdocs --strict` reclama de page sem `nav` entry | Média | Adicionar ao `nav:` antes do build |
| README fica longo demais | Baixa | Detalhes profundos vão pra mkdocs, README só linka |
| CHANGELOG numérico (vs. `[Unreleased]`) — projeto pode ter convenção | Verificar antes | Olhar últimas entradas do CHANGELOG |

---

**End of Specification**
