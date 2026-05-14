# Vulpcode

**A terminal coding agent that lets you choose the model.**

[![PyPI](https://img.shields.io/pypi/v/vulpcode.svg)](https://pypi.org/project/vulpcode/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#status)

Vulpcode is a CLI agent for software engineering tasks — inspired by Claude
Code — that is **provider-agnostic**. The same set of tools, slash commands,
and MCP support, but you decide which model to talk to: paid APIs
(Anthropic, OpenAI, Gemini), local engines (Ollama, LM Studio, vLLM),
OpenAI-compatible gateways (DeepSeek, Groq, OpenRouter), or internal
corporate endpoints.

---

## Highlights

- **Provider-agnostic.** Switch models with a single flag (`--provider`,
  `--model`), without changing your workflow.
- **Privacy-first.** Run fully offline with Ollama, LM Studio, or vLLM. No
  outbound traffic when the chosen provider is local.
- **Pip-native.** Installs like any Python package. No Node, no npm, no
  external runtime.
- **Tool-complete.** Functional parity with the leading agentic CLIs: Bash
  (foreground + background), Read, Write, Edit, MultiEdit, Glob, Grep,
  WebFetch, WebSearch, Task, TodoWrite, NotebookEdit.
- **MCP support.** Connects to any Model Context Protocol server you
  configure; their tools are auto-registered into the agent.
- **Hackable.** ~3k lines of core code, tools as plugins, providers as
  adapters.

---

## Installation

Requires **Python 3.11+**.

```bash
pip install vulpcode
```

Installing inside a virtual environment is recommended:

```bash
python -m venv ~/.venv/vulpcode
source ~/.venv/vulpcode/bin/activate
pip install vulpcode
```

Vulpcode ships two equivalent console scripts: `vulp` (short) and `vulpcode`.

### Optional extras

| Extra      | Adds                                                                      | Use it for                              |
| ---------- | ------------------------------------------------------------------------- | --------------------------------------- |
| `[dev]`    | `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `respx`                       | Contributors running the test suite     |
| `[docs]`   | `mkdocs`, `mkdocs-material`, `mkdocstrings[python]`, `pymdown-extensions` | Building the documentation site         |
| `[search]` | `duckduckgo-search`                                                       | Using `WebSearch` without a Tavily key  |

```bash
pip install "vulpcode[search]"
pip install "vulpcode[dev,docs]"
```

### From source

```bash
git clone https://github.com/Vulp-Code/vulpcode.git
cd vulpcode
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs,search]"
```

---

## Quick start

```bash
# Verify the install
vulp --version
vulp providers
```

### First chat with Claude

```bash
export ANTHROPIC_API_KEY=sk-ant-...
vulp --auto "say hi in one word"
```

### Run fully offline with Ollama

```bash
ollama pull qwen2.5-coder:7b
vulp --provider ollama --model qwen2.5-coder:7b --auto "explain git rebase"
```

### Use an OpenAI-compatible gateway (e.g. Groq)

```bash
export GROQ_API_KEY=gsk_...
vulp --provider groq --model llama-3.3-70b-versatile
```

### Use an internal corporate endpoint

```bash
export INTERNAL_LLM_ENDPOINT="https://internal.example.com/v1/chat"
export INTERNAL_LLM_USER_UUID="00000000-0000-0000-0000-000000000000"
vulp --provider internal-llm
```

---

## Supported providers

| Provider       | Backend type          | Tools | Vision | Streaming |
| -------------- | --------------------- | :---: | :----: | :-------: |
| `anthropic`    | Anthropic (Claude)    |   x   |   x    |    x      |
| `openai`       | OpenAI (GPT)          |   x   |   x    |    x      |
| `gemini`       | Google (Gemini)       |   x   |   x    |    x      |
| `ollama`       | Local                 |   x   |   x    |    x      |
| `deepseek`     | OpenAI-compatible     |   x   |        |    x      |
| `groq`         | OpenAI-compatible     |   x   |        |    x      |
| `openrouter`   | OpenAI-compatible     |   x   |        |    x      |
| `lmstudio`     | Local                 |   x   |        |    x      |
| `vllm`         | Local                 |   x   |        |    x      |
| `internal-llm` | Corporate endpoint    |       |        |           |

Run `vulp providers` to list them at any time.

---

## Built-in tools

| Tool           | Purpose                                                |
| -------------- | ------------------------------------------------------ |
| `Read`         | Read files (text, images, notebooks, PDFs)             |
| `Write`        | Create or overwrite a file                             |
| `Edit`         | Exact string replacement                               |
| `MultiEdit`    | Multiple edits in a single file, atomically            |
| `Bash`         | Run shell commands                                     |
| `BashOutput`   | Stream output from a long-running background process   |
| `KillBash`     | Terminate a background process                         |
| `Glob`         | Find files by pattern                                  |
| `Grep`         | Search file contents                                   |
| `WebFetch`     | Fetch and parse a URL                                  |
| `WebSearch`    | Search the web (Tavily or DuckDuckGo)                  |
| `Task`         | Delegate work to a sub-agent                           |
| `TodoWrite`    | Persistent task list inside a session                  |
| `NotebookEdit` | Edit Jupyter notebook cells                            |

---

## Slash commands

Available inside the REPL:

| Command                    | What it does                                  |
| -------------------------- | --------------------------------------------- |
| `/help`                    | Show all commands                             |
| `/clear`                   | Clear the screen and conversation history     |
| `/exit`                    | Leave the REPL                                |
| `/tools`                   | List enabled tools                            |
| `/cost`                    | Show token usage and estimated cost           |
| `/compact`                 | Compact the conversation to free context      |
| `/provider <name>`         | Switch provider                               |
| `/model <id>`              | Switch model on the current provider          |
| `/save <name>`             | Save the current session                      |
| `/load <name>`             | Restore a saved session                       |
| `/mcp`                     | Inspect connected MCP servers                 |

---

## Permission modes

Vulpcode never executes tools silently by default. Choose a mode that
matches your trust level for the current task:

| Mode      | Flag        | Behavior                                                          |
| --------- | ----------- | ----------------------------------------------------------------- |
| `default` |             | Read tools auto-run; writes and Bash require confirmation         |
| `auto`    | `--auto`    | Auto-approve every tool call                                      |
| `safe`    | `--safe`    | Confirm every tool call, including reads                          |
| `plan`    | `--plan`    | Plan-only — the agent proposes actions but executes nothing       |

Headless mode for scripting:

```bash
vulp --print --auto "refactor src/utils.py to remove duplication"
```

Resume your last session:

```bash
vulp --resume
```

---

## MCP (Model Context Protocol)

MCP servers declared in `~/.vulpcode/config.toml` are launched
automatically. Their tools are added to the registry with the prefix
`mcp__<server>__<tool>` and become available like native tools.

Minimal config:

```toml
[mcp.servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/home/me/projects"]
```

Inspect runtime state with `/mcp` inside the REPL.

---

## Configuration

Vulpcode reads configuration in this order:

1. CLI flags (`--provider`, `--model`, ...)
2. Environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
   `GEMINI_API_KEY`, `OLLAMA_HOST`, `INTERNAL_LLM_ENDPOINT`, ...)
3. `~/.vulpcode/config.toml`

Sessions, history, and per-project state live under `~/.vulpcode/`.

---

## Status

Alpha. The CLI surface, tool set, and config format may still change
before 1.0. See [CHANGELOG.md](CHANGELOG.md) for release notes.

---

## Documentation

Full documentation, including detailed configuration, recipes, the API
reference, and architecture notes, is built with MkDocs from the `docs/`
directory.

```bash
pip install "vulpcode[docs]"
mkdocs serve
```

---

## Contributing

Issues and pull requests are welcome. To set up a development environment:

```bash
git clone https://github.com/Vulp-Code/vulpcode.git
cd vulpcode
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs,search]"
pytest
ruff check .
mypy
```

---

## License

MIT — see [LICENSE](LICENSE).

---

## Links

- Source code: <https://github.com/Vulp-Code/vulpcode>
- Issues: <https://github.com/Vulp-Code/vulpcode/issues>
- PyPI: <https://pypi.org/project/vulpcode/>
