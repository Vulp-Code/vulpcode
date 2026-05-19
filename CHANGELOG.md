# Changelog

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
