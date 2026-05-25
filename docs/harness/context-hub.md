# Context Hub

The Context Hub offloads large tool outputs to disk so they don't flood the model's
context window.  When a `ToolResult` exceeds the configured character threshold the
full content is written to a file under `~/.vulpcode/handles/<session_id>/` and the
model receives a compact summary containing:

- A header with the handle URI, total chars, and line count.
- A head preview (first N lines).
- A tail preview (last M lines).
- Instructions to call `HandleRead` for specific line ranges.

## Configuration

```toml
[middleware.context_hub]
enabled = true
threshold_chars = 4000          # outputs larger than this go to disk
preview_head_lines = 30
preview_tail_lines = 10
storage_dir = "~/.vulpcode/handles"
keep_handles_days = 7
```

## HandleRead tool

Use `HandleRead` to retrieve a slice of an offloaded output:

```
HandleRead(handle="2026-05-25_14-03-22_Bash_a1b2c3.txt", lines="100-200")
HandleRead(handle="...", lines="all", grep="error")
```

## Cleanup

On startup, handles older than `keep_handles_days` days are automatically removed
across all session sub-directories.
