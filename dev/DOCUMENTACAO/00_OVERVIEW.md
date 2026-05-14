# Plano de Documentacao — Vulpcode (MkDocs Material)

**Status**: PENDENTE
**Data**: 2026-05-06
**Target**: `/home/guhaase/projetos/vulpcode/docs/` (a ser criado pela FASE 01)

---

## Contexto

Vulpcode hoje tem o codigo completo (14 fases concluidas em `dev/`) mas falta
uma documentacao "completa", publicavel, com mesmo padrao de qualidade do
projeto `panelbox` (`/home/guhaase/projetos/panelbox/docs`). A documentacao
sera construida em **MkDocs com tema Material**, gerada incrementalmente em
13 fases por este plano.

**Estado inicial**: pasta vazia (`docs/` ainda nao existe).
**Estado final**: site MkDocs servivel via `mkdocs serve`, com landing,
quickstart, guides, referencia de providers, referencia de tools, API auto-
gerada via `mkdocstrings`, recipes, arquitetura, contributing, FAQ.

---

## Princípios

1. **Cada arquivo de tarefa e auto-contido** — instrui exatamente quais arquivos
   `.md` criar, com que conteudo, citando os modulos do codigo a consultar.
2. **Avanco por checkbox** — Claude marca `- [ ]` -> `- [x]` ao concluir cada
   criterio. `prompt.sh` itera ate zerar.
3. **Fonte da verdade e o codigo** — todo conteudo doc vem de `src/vulpcode/`,
   nao de imaginacao. Toda doc deve ser cross-referenced com os modulos.
4. **Portugues como idioma principal** (consistente com a especificacao do
   projeto), exceto:
   - `mkdocs.yml` em ingles (padrao internacional)
   - Snippets de codigo em ingles (consistente com codigo)
   - Comentarios em codigo em ingles
5. **Link cross-page liberal** — doc enxuto que conecta entre si, nao ladrilho
   gigante.

---

## Stack

| Camada | Tecnologia | Notas |
|--------|------------|-------|
| Static site | **MkDocs** | `pip install mkdocs` |
| Tema | **Material for MkDocs** | `pip install mkdocs-material` |
| API auto | **mkdocstrings[python]** | extrai docstrings de `src/vulpcode/` |
| Diagramas | **mkdocs-mermaid2-plugin** | opcional, para arquitetura |
| Versionamento | **mike** | opcional, para v0.1, v0.2... |

Adicionar em `pyproject.toml` `[project.optional-dependencies].docs`.

---

## Estrutura final esperada

```
docs/
├── index.md                        # landing
├── assets/
│   └── images/
│       ├── logo.svg
│       └── favicon.svg
├── stylesheets/
│   └── extra.css
├── getting-started/
│   ├── index.md
│   ├── installation.md
│   ├── quickstart.md
│   ├── first-config.md
│   └── core-concepts.md
├── user-guide/
│   ├── index.md
│   ├── using-the-repl.md
│   ├── slash-commands.md
│   ├── permission-modes.md
│   ├── sessions.md
│   └── keyboard-shortcuts.md
├── providers/
│   ├── index.md
│   ├── anthropic.md
│   ├── openai-family.md          # OpenAI + DeepSeek + Groq + OpenRouter + LM Studio + vLLM
│   ├── gemini.md
│   ├── ollama.md
│   ├── internal-llm.md
│   └── switching-at-runtime.md
├── tools/
│   ├── index.md
│   ├── filesystem.md             # Read/Write/Edit/MultiEdit/Glob
│   ├── shell.md                  # Bash/BashOutput/KillBash
│   ├── search.md                 # Grep
│   ├── web.md                    # WebFetch/WebSearch
│   └── agent.md                  # TodoWrite/Task/NotebookEdit
├── configuration/
│   ├── index.md
│   ├── config-toml.md
│   ├── env-vars.md
│   └── permissions.md
├── mcp/
│   └── index.md
├── recipes/
│   ├── index.md
│   ├── review-pr.md
│   ├── refactor-code.md
│   ├── write-tests.md
│   ├── debug-bug.md
│   ├── generate-docs.md
│   └── offline-with-ollama.md
├── api/
│   ├── index.md
│   ├── providers.md
│   ├── tools.md
│   ├── agent.md
│   ├── permissions.md
│   ├── config.md
│   ├── session.md
│   └── mcp.md
├── architecture/
│   ├── index.md
│   ├── agent-loop.md
│   ├── streaming.md
│   ├── provider-translation.md
│   └── tool-registry.md
├── contributing/
│   ├── index.md
│   ├── dev-setup.md
│   ├── add-provider.md
│   ├── add-tool.md
│   └── code-conventions.md
├── faq.md
└── changelog.md                  # link/include do CHANGELOG.md raiz
```

E na raiz: `mkdocs.yml`.

---

## Resumo das Fases

| Fase | Pasta                          | Descricao                                | Tarefas |
|------|--------------------------------|------------------------------------------|---------|
| 01   | FASE_01_BOOTSTRAP_MKDOCS       | mkdocs.yml + tema + assets + landing     | 3       |
| 02   | FASE_02_GETTING_STARTED        | install, quickstart, conceitos           | 3       |
| 03   | FASE_03_USER_GUIDE_REPL        | REPL, slash, permissions, sessoes        | 3       |
| 04   | FASE_04_PROVIDERS              | overview + dedicated + openai-family + internal-llm | 4 |
| 05   | FASE_05_TOOLS                  | overview + filesystem/shell + agent/web  | 3       |
| 06   | FASE_06_CONFIGURACAO           | config.toml + env + permissions detalhe  | 2       |
| 07   | FASE_07_MCP                    | guia MCP                                 | 1       |
| 08   | FASE_08_RECEITAS               | dev recipes + ops recipes                | 2       |
| 09   | FASE_09_API_REFERENCE          | API auto-doc (mkdocstrings)              | 3       |
| 10   | FASE_10_ARQUITETURA            | internals do agent + providers           | 2       |
| 11   | FASE_11_CONTRIBUTING           | dev setup + extending                    | 2       |
| 12   | FASE_12_FAQ                    | FAQ + troubleshooting                    | 1       |
| 13   | FASE_13_BUILD_FINAL            | verificar links + build sem warning      | 2       |

**Total**: 13 fases, 31 tarefas.

---

## Ordem de Execucao

Sequencial — cada fase depende da anterior em algum grau. Especialmente:

- FASE 01 (mkdocs.yml) bloqueia tudo depois (sem nav nao tem doc).
- FASE 02 (getting-started) — entrada do usuario novo.
- FASE 04 (providers) bloqueia FASE 05 (tools), 06 (config), 08 (recipes).
- FASE 09 (api-reference) precisa que docstrings em `src/` estejam OK — pode
  exigir voltar e melhorar docstrings em algumas tarefas.
- FASE 13 (build final) e ultima.

A ordem na lista `TASK_FILES` no `prompt.sh` respeita estas dependencias.

---

## Automacao

| Arquivo | Funcao |
|---------|--------|
| `prompt.sh` | Itera por todas as tarefas e chama Claude CLI ate zero pendentes |
| `LOG/` | Logs por iteracao + status atual |

Para acompanhar:

```bash
# log em tempo real
tail -f /home/guhaase/projetos/vulpcode/dev/DOCUMENTACAO/LOG/latest.log

# status rapido
cat /home/guhaase/projetos/vulpcode/dev/DOCUMENTACAO/LOG/status.txt
```

---

## Criterio de Sucesso (Final)

- [ ] Todas as 13 fases concluidas (`grep -c "^- \[ \]" dev/DOCUMENTACAO/**/*.md` retorna 0)
- [ ] `mkdocs build --strict` no project root completa sem warnings
- [ ] `mkdocs serve` mostra a doc em `http://localhost:8000` com nav completa
- [ ] Todos os links internos (`[texto](caminho.md)`) resolvem
- [ ] API reference auto-gerada via mkdocstrings cobre `Provider`, `Tool`, `Agent`, `PermissionManager`
- [ ] `pyproject.toml` tem `[project.optional-dependencies].docs` com mkdocs-material e mkdocstrings
- [ ] Logo SVG criado e referenciado em `assets/images/logo.svg`
- [ ] CHANGELOG da raiz integrado em `docs/changelog.md`

---

**End of Document**
