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
