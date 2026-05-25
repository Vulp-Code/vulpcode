"""VFS: Virtual File System abstraction for Vulpcode tools.

Backends:
- ``local``   — delegates to the local filesystem (default).
- ``jail``    — restricts operations to a directory root; raises VFSError on escape.
- ``sandbox`` — stub for future container/remote execution (not yet implemented).

Configuration (``config.toml``)::

    [vfs]
    backend = "local"   # local | jail | sandbox
    jail_root = ""      # required when backend = "jail"
"""
from __future__ import annotations

from vulpcode.vfs.jail import JailBackend
from vulpcode.vfs.local import LocalBackend
from vulpcode.vfs.protocol import VFSBackend, VFSError, VFSStat
from vulpcode.vfs.sandbox import SandboxBackend

_VALID_BACKENDS = ("local", "jail", "sandbox")


def build_vfs(config: dict | None = None) -> LocalBackend | JailBackend | SandboxBackend:
    """Instantiate a VFSBackend from a config dict.

    Args:
        config: Dict with keys ``backend`` (str) and optionally ``jail_root``
            (str, required when ``backend="jail"``). ``None`` returns a
            ``LocalBackend``.

    Returns:
        A VFSBackend instance.

    Raises:
        ValueError: Unknown backend name or missing ``jail_root``.
    """
    cfg = config or {}
    backend_name = cfg.get("backend", "local")
    if backend_name == "local":
        return LocalBackend()
    if backend_name == "jail":
        jail_root = cfg.get("jail_root", "")
        if not jail_root:
            raise ValueError(
                "vfs.jail_root is required when vfs.backend='jail'. "
                "Set it to the directory root to confine all file operations."
            )
        return JailBackend(jail_root)
    if backend_name == "sandbox":
        return SandboxBackend()
    raise ValueError(
        f"Unknown vfs backend: {backend_name!r}. "
        f"Valid options: {', '.join(_VALID_BACKENDS)}"
    )


__all__ = [
    "VFSBackend",
    "VFSError",
    "VFSStat",
    "LocalBackend",
    "JailBackend",
    "SandboxBackend",
    "build_vfs",
]
