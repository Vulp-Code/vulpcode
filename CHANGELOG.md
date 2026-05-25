# Changelog

## [Unreleased]

### Added
- **Harness** — opt-in middleware layer wired into the agent loop via `HookBus`:
  - `eviction`: drop old assistant+tool pairs when message count or token budget is exceeded (`EvictionConfig`).
  - `summarization`: auto-compact history once estimated token count exceeds `trigger_at_tokens`; respects cooldown between summarizations (`SummarizationConfig`).
  - `context_hub`: offload large tool outputs to disk; model receives a compact header + preview + `HandleRead` instructions (`ContextHubConfig`).
  - `skills`: load specialist playbooks from `~/.vulpcode/skills/`; each skill can restrict the available tool set via `tools_allow` (`SkillsConfig`).
  - `profiles`: named configuration bundles (`--profile safe`, `--profile code`) stored in TOML; set system_prompt_extra, tools_allow, and middleware defaults.
  - `tool_patch`: intercept tool calls before execution with per-rule `block`, `redact`, or `log_only` actions (`ToolPatchConfig`).
  - `VFS` backends: `local` (default), `jail` (confines file ops to a `jail_root`), and `sandbox` stub.
- **Safety integrations** wired into tool implementations:
  - `Write`, `Edit`, `MultiEdit`, `_validated_write`: secret scanning via `scan_secrets()`.
  - `Write`: sandbox path check via `check_path_sandbox()`.
  - `Bash`: catastrophic command blocking + risky command warning via `classify_command()`.
  - `Edit`, `MultiEdit`: post-edit revalidation via `validate_after_edit()`.
  - `WriteToml`: `pyproject.toml` schema validation (requires `[build-system]` + version).
  - `WritePy`: ruff lint (when ruff is available) + smoke import check.
- `Agent` accepts `hook_bus` parameter; hooks receive a `LoopState` with `messages`, `usage`, `iteration`, and `metadata`.
- `session.py` exports `_current_state` (ContextVar) and `skill_registry` for harness access.
- Integration test suite (`tests/test_harness_integration/`) with 8 end-to-end scenarios and subprocess smoke tests.

## [0.2.0] - 2026-05-18

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

## [0.1.1] - 2026-05-14

- Expanded English README with installation, providers table, tools table,
  slash commands, permission modes, MCP example, and contributing guide.
- No functional changes.

## [0.1.0] - 2026-05-06

Initial release. Multi-provider terminal coding agent with:
- Providers: Anthropic, OpenAI (+ DeepSeek/Groq/OpenRouter), Gemini, Ollama
- Tools: Read, Write, Edit, MultiEdit, Bash (+ background), Glob, Grep, WebFetch, WebSearch, Task, TodoWrite, NotebookEdit
- MCP client
- Slash commands: /help /clear /exit /tools /cost /compact /provider /model /save /load /mcp
- Session persistence with --resume
- Permission modes: default, auto, safe, plan
