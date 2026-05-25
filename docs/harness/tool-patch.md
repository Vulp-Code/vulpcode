# Tool Patch Middleware

The `tool_patch` middleware intercepts tool calls before execution to **redact** sensitive
values, **block** dangerous calls, or **log** matches without changing behavior.

## Configuration

Enable in your `config.toml`:

```toml
[middleware.tool_patch]
enabled = true

[[middleware.tool_patch.rules]]
tool = "Bash"
match = { command = "(?i)(secret_key|api_token)\\s*=\\s*\\S+" }
action = "redact"
replace = "\\1=***REDACTED***"

[[middleware.tool_patch.rules]]
tool = "Bash"
match = { command = "(?i)\\brm\\s+-rf\\s+/" }
action = "block"
message = "Refused: rm -rf / blocked by tool_patch."

[[middleware.tool_patch.rules]]
tool = "Read"
match = { file_path = "^/etc/(passwd|shadow)$" }
action = "block"
message = "Refused: system files blocked."

[[middleware.tool_patch.rules]]
tool = "*"
match = { "*" = "(?i)password\\s*[:=]\\s*\\S+" }
action = "redact"
replace = "password=***REDACTED***"
```

## Rule Fields

| Field     | Type     | Description                                                    |
|-----------|----------|----------------------------------------------------------------|
| `tool`    | str      | Tool name or `"*"` for any tool.                               |
| `match`   | dict     | Map of `arg_name -> regex`. Use `"*"` to match any argument.   |
| `action`  | str      | `"redact"`, `"block"`, or `"log_only"`.                        |
| `replace` | str      | Regex replacement string (only for `redact`).                  |
| `message` | str      | Error message returned to the model (only for `block`).        |

## Actions

- **`redact`**: Applies `re.sub(pattern, replace, value)` to matching arguments.
  Returns a new `ToolCall` with the substituted arguments.
- **`block`**: Prevents execution entirely. The model receives an error message
  with the configured `message` text.
- **`log_only`**: Logs a `WARNING` but passes the call through unchanged.

## Rule Ordering

Rules are evaluated in declaration order. The **first matching rule** wins.

## Audit Logging

All decisions are logged at `INFO` level via `vulpcode.harness.tool_patch`:

```
[redact] Bash command: substituted 1 occurrence(s) of /secret_key.../
[block]  Read file_path=/etc/passwd: blocked by rule #2
```
