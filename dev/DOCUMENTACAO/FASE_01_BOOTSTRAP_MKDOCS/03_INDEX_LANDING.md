# Tarefa 01.03 - Landing Page (index.md)

**Status**: PENDENTE
**Fase**: 01 - Bootstrap MkDocs
**Dependencias**: 01.01 (mkdocs setup), 01.02 (logo)
**Bloqueia**: nada diretamente, mas e a primeira pagina que o usuario ve

---

## Objetivo

Substituir o `docs/index.md` placeholder por uma landing real: pitch curto,
quickstart de 3 abas (instalacao, primeiro chat, troca de provider), tabela
de providers, lista de tools, links para getting-started, user-guide, e API.

---

## Arquivo a editar

- `/home/guhaase/projetos/vulpcode/docs/index.md`

---

## Conteudo

```markdown
---
title: Vulpcode — Terminal Coding Agent multi-provedor
description: CLI agentica de programacao em Python. Funciona com Claude, OpenAI, Gemini, Ollama e endpoints internos.
---

<div class="home-logo" markdown>
  ![Vulpcode](assets/images/logo_text.svg)
</div>

**A CLI de programacao agentica que voce escolhe o modelo.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
![Status](https://img.shields.io/badge/status-alpha-orange.svg)

Vulpcode e uma CLI inspirada em Claude Code, **multi-provider** (Anthropic,
OpenAI, Gemini, Ollama, DeepSeek, Groq, OpenRouter, LM Studio, vLLM, e endpoints
corporativos). Mesma experiencia de tools, slash commands e MCP — mas voce
decide com qual modelo conversar.

[Comecar agora](getting-started/quickstart.md){ .md-button .md-button--primary }
[Ver providers](providers/index.md){ .md-button }
[Codigo no GitHub](https://github.com/vulpcode/vulpcode){ .md-button }

---

## Quick start

=== "Instalar"

    ```bash
    pip install vulpcode
    ```

=== "Primeiro chat (Claude)"

    ```bash
    export ANTHROPIC_API_KEY=sk-ant-...
    vulp --auto "diga oi em uma palavra"
    # Ola!
    ```

=== "Trocar para Ollama (offline)"

    ```bash
    ollama pull qwen2.5-coder:7b
    vulp --provider ollama --model qwen2.5-coder:7b --auto "explique git rebase"
    ```

=== "Endpoint corporativo"

    ```bash
    export INTERNAL_LLM_ENDPOINT="http://internal.example.com/v1/chat"
    export INTERNAL_LLM_USER_UUID="00000000-0000-0000-0000-000000000000"
    vulp --provider internal-llm
    ```

---

## Por que vulpcode?

- **Provider-agnostic** — troque de modelo num unico comando, sem mudar workflow.
- **Privacy-first** — funciona 100% offline com Ollama.
- **Pip-native** — instala como qualquer pacote Python, sem npm/Node.
- **Tool-complete** — paridade funcional com Claude Code: Bash, Read, Write,
  Edit, Glob, Grep, WebFetch, WebSearch, Task, TodoWrite, MCP.
- **Hackeavel** — nucleo de ~3k linhas, tools como plugins, providers como adapters.

---

## Providers suportados

| Provider       | Tipo                | Tools | Vision | Streaming |
|----------------|---------------------|-------|--------|-----------|
| `anthropic`    | API paga (Claude)   | OK    | OK     | OK        |
| `openai`       | API paga (GPT)      | OK    | OK     | OK        |
| `gemini`       | API paga (Google)   | OK    | OK     | OK        |
| `ollama`       | Local / privado     | OK    | OK     | OK        |
| `deepseek`     | OpenAI-compatible   | OK    | -      | OK        |
| `groq`         | OpenAI-compatible   | OK    | -      | OK        |
| `openrouter`   | OpenAI-compatible   | OK    | -      | OK        |
| `lmstudio`     | Local / privado     | OK    | -      | OK        |
| `vllm`         | Local / privado     | OK    | -      | OK        |
| `internal-llm` | Endpoint corporativo| -     | -      | -         |

[Ver detalhes →](providers/index.md)

---

## Tools nativas

`Read` `Write` `Edit` `MultiEdit` `Glob` `Grep` `Bash` `BashOutput` `KillBash`
`WebFetch` `WebSearch` `Task` `TodoWrite` `NotebookEdit`

[Documentacao das tools →](tools/index.md)

---

## Suporte a MCP

Servidores MCP (Model Context Protocol) sao iniciados automaticamente conforme
configurados em `~/.vulpcode/config.toml`. Tools expostas via MCP entram no
registry com prefixo `mcp__<server>__<tool>`.

[Como usar MCP →](mcp/index.md)

---

## Proximos passos

- [Instalacao detalhada](getting-started/installation.md)
- [Primeira configuracao](getting-started/first-config.md)
- [Conceitos principais](getting-started/core-concepts.md)
- [Lista de slash commands](user-guide/slash-commands.md)
- [Receitas (cookbook)](recipes/index.md)
- [Referencia da API](api/index.md)

---

## Licenca

MIT — veja [`LICENSE`](https://github.com/vulpcode/vulpcode/blob/main/LICENSE).
```

---

## Atualizar `mkdocs.yml`

A landing ja existe no nav (`Home: index.md`). Esta tarefa NAO altera o nav —
isso e feito pelas fases seguintes que adicionam novas paginas.

---

## INSTRUCAO CRITICA

- Os links para `getting-started/`, `user-guide/`, `providers/`, `tools/`, `mcp/`,
  `recipes/`, `api/` ainda nao tem destinos validos. **Esses links vao quebrar**
  no `mkdocs build --strict`.
- **Solucao**: rodar `mkdocs build` (sem `--strict`) durante esta tarefa, e
  aceitar warnings sobre links quebrados. Eles serao resolvidos nas tarefas
  seguintes que criam essas paginas.
- A FASE 13.01 fara a validacao final com `--strict`.
- Nao mude o tema/cores, apenas o conteudo.

---

## Etapas de Implementacao

### Etapa 1: Sobrescrever `docs/index.md` com o conteudo acima

### Etapa 2: Verificar com `mkdocs serve`

Abrir http://localhost:8000 e conferir:
- Logo aparece no topo da home
- Botoes "Comecar agora", "Ver providers", "GitHub" estao alinhados
- Tabela de providers renderiza
- Tabs de quickstart funcionam (clicar para alternar)

### Etapa 3: Build (sem `--strict` por enquanto)

```bash
cd /home/guhaase/projetos/vulpcode
mkdocs build
```

Warnings sobre links quebrados sao esperados.

---

## Criterios de Aceite

- [x] `docs/index.md` substituido pelo conteudo da landing real
- [x] Front matter com title e description presente
- [x] Logo (logo_text.svg) referenciado no topo
- [x] 4 tabs de quickstart (Instalar, Primeiro chat, Ollama, Endpoint corporativo)
- [x] Tabela de providers presente com 10 entradas
- [x] Lista de tools listada
- [x] Botoes de call-to-action (md-button) presentes
- [x] `mkdocs serve` exibe a landing sem erros visuais
- [x] `mkdocs build` (sem --strict) completa

---

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| Links quebrados bloqueiam build | Usar `mkdocs build` (nao --strict) ate FASE 13 |
| Botoes nao renderizam | Material exige sintaxe `{ .md-button }` exata |
| SVG nao aparece | Conferir que `logo_text.svg` foi criado em 01.02 |

---

**End of Specification**
