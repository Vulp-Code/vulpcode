# VFS Backends

Vulpcode routes all file-tool operations through a `VFSBackend` abstraction.
This lets you swap the underlying filesystem without changing any tool logic.

## Configuration

```toml
[vfs]
backend = "local"   # local | jail | sandbox
jail_root = ""      # required when backend = "jail"
```

## Backends

### `local` (default)

Delegates directly to the local filesystem via `pathlib` / `os`. Writes are
atomic (temp-file + rename). Behavior is identical to Vulpcode before this
feature was added.

### `jail`

Confines all file-tool operations to a single root directory. Any path that
resolves outside `jail_root` raises `VFSError` and is returned to the model
as a tool error. Useful for:

- Running the agent against a checked-out repo in CI without risk of
  accidentally writing outside the repo root.
- Sandboxing untrusted prompts to a scratch directory.

**Limitation**: `Bash` tool calls are **not** subject to jail restrictions —
only VFS-aware file tools (Read, Write, Edit, Glob, Grep, Tree, Write*) respect
the jail boundary. Bash continues to operate on the real filesystem.

Example:

```toml
[vfs]
backend = "jail"
jail_root = "/workspace/myproject"
```

### `sandbox` (planned)

**Not yet implemented.** A future backend will delegate file operations to an
isolated container (Docker, Firecracker) or remote execution environment.

Roadmap:
1. Define a container API adapter implementing `VFSBackend`.
2. Wire each method to the container exec / HTTP API.
3. Register `"sandbox"` in `build_vfs`.

All methods currently raise `NotImplementedError` with a pointer to this file.

## Extending

Implement the `VFSBackend` protocol from `vulpcode.vfs.protocol`:

```python
from vulpcode.vfs.protocol import VFSBackend, VFSStat, VFSError

class MyBackend:
    name = "mybackend"

    def read_text(self, path: str, *, encoding: str = "utf-8") -> str:
        ...
    # ... implement all methods
```

Then register it in `vulpcode/vfs/__init__.py` → `build_vfs`.
