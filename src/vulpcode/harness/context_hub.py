"""Context Hub: offload large tool outputs to disk and return a handle + preview.

When a ToolResult exceeds ``threshold_chars``, the full content is written to a
file under ``~/.vulpcode/handles/<session_id>/`` and the model receives a compact
summary with a head/tail preview and a ``HandleRead`` instruction.

Opt-in via config::

    [middleware.context_hub]
    enabled = true
    threshold_chars = 4000
    storage_dir = "~/.vulpcode/handles"
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from vulpcode.tools.base import ToolResult

logger = logging.getLogger("vulpcode.harness.context_hub")

_SEP = "─" * 25  # Unicode box-drawing horizontal line


@dataclass
class ContextHubConfig:
    """Configuration for the context hub middleware.

    Fields:
        enabled: Activate the context hub.
        threshold_chars: Offload outputs whose character count exceeds this.
        preview_head_lines: Lines to show in the head preview block.
        preview_tail_lines: Lines to show in the tail preview block.
        storage_dir: Base directory; session sub-directories are created here.
        keep_handles_days: Handles older than this many days are deleted on startup.
    """

    enabled: bool = False
    threshold_chars: int = 4000
    preview_head_lines: int = 30
    preview_tail_lines: int = 10
    storage_dir: Path = field(default_factory=lambda: Path.home() / ".vulpcode" / "handles")
    keep_handles_days: int = 7


class ContextHub:
    """Middleware that offloads large tool outputs to disk.

    Usage::

        hub = ContextHub(config, session_id)
        bus.register("after_tool_call", hub)
    """

    def __init__(self, config: ContextHubConfig, session_id: str) -> None:
        self.config = config
        self.dir = config.storage_dir.expanduser() / session_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_old(config.keep_handles_days)

    # ------------------------------------------------------------------
    # Hook protocol metadata
    # ------------------------------------------------------------------

    name = "context_hub"
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cleanup_old(self, days: int) -> None:
        """Remove handle files older than *days* across all session sub-dirs."""
        import time

        cutoff = time.time() - days * 86400
        base = self.config.storage_dir.expanduser()
        removed = 0
        if base.exists():
            for p in base.rglob("*.txt"):
                try:
                    if p.stat().st_mtime < cutoff:
                        p.unlink()
                        removed += 1
                except OSError:
                    pass
        if removed:
            logger.info(
                "context_hub: removed %d stale handle(s) older than %d days",
                removed,
                days,
            )

    def _resolve_handle(self, handle: str) -> Path:
        """Resolve *handle* to an absolute path, rejecting path-traversal attempts."""
        if "/" in handle or ".." in handle or handle.startswith("."):
            raise ValueError(f"invalid handle: {handle!r}")
        path = self.dir / handle
        # Guarantee the resolved path stays inside self.dir.
        path.resolve().relative_to(self.dir.resolve())
        return path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def offload(self, *, tool_name: str, content: str) -> str:
        """Write *content* to disk and return the handle filename.

        Filename pattern: ``YYYY-MM-DD_HH-MM-SS_<tool_name>_<6hex>.txt``.
        """
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        short_id = uuid.uuid4().hex[:6]
        filename = f"{ts}_{tool_name}_{short_id}.txt"
        path = self.dir / filename
        path.write_text(content, encoding="utf-8")
        logger.info(
            "context_hub: offloaded %d chars from '%s' to %s",
            len(content),
            tool_name,
            filename,
        )
        return filename

    def _build_handle_message(self, filename: str, content: str) -> str:
        """Construct the replacement message shown to the model."""
        all_lines = content.splitlines()
        n_chars = len(content)
        n_lines = len(all_lines)

        head = all_lines[: self.config.preview_head_lines]
        # Only show tail when content has more lines than the head window.
        if n_lines > self.config.preview_head_lines:
            tail = all_lines[-self.config.preview_tail_lines :]
        else:
            tail = []

        parts: list[str] = [
            f"[OFFLOADED to handle://{filename} — {n_chars} chars / {n_lines} lines]",
            "",
            f"PREVIEW (first {len(head)} lines):",
            _SEP,
        ]
        parts.extend(head)
        parts.append(_SEP)

        if tail:
            parts.append("")
            parts.append(f"PREVIEW (last {len(tail)} lines):")
            parts.append(_SEP)
            parts.extend(tail)
            parts.append(_SEP)

        parts.append("")
        parts.append(
            f'Use HandleRead(handle="{filename}", lines="100-200")\n'
            'to view a slice. Use lines="all" only if the full content is essential.'
        )
        return "\n".join(parts)

    def read_slice(
        self,
        handle: str,
        *,
        lines: str,
        grep: str | None,
        max_chars: int,
    ) -> str:
        """Return a slice of an offloaded handle, optionally filtered by *grep*.

        Args:
            handle: Filename returned by :meth:`offload`.
            lines: Line range like ``"1-200"`` or ``"all"``.
            grep: Optional regex; only matching lines are returned when set.
            max_chars: Truncate result to this many characters.

        Returns:
            The selected (and optionally filtered) text.

        Raises:
            ValueError: For an invalid handle name or lines spec.
            FileNotFoundError: If the handle file does not exist.
        """
        path = self._resolve_handle(handle)
        if not path.exists():
            raise FileNotFoundError(f"handle not found: {handle!r}")

        content = path.read_text(encoding="utf-8")
        all_lines = content.splitlines()

        if lines == "all":
            selected = all_lines
        else:
            m = re.match(r"^(\d+)-(\d+)$", lines)
            if not m:
                raise ValueError(
                    f"invalid lines spec: {lines!r}; use 'N-M' (e.g. '1-200') or 'all'"
                )
            start = max(1, int(m.group(1))) - 1  # convert to 0-indexed
            end = int(m.group(2))  # exclusive end in slice
            selected = all_lines[start:end]

        if grep is not None:
            pattern = re.compile(grep)
            selected = [ln for ln in selected if pattern.search(ln)]

        result = "\n".join(selected)
        if len(result) > max_chars:
            marker = f"\n[TRUNCATED: showing first {max_chars} chars of {len(result)} total]"
            result = result[:max_chars] + marker
        return result

    # ------------------------------------------------------------------
    # Hook callable
    # ------------------------------------------------------------------

    def __call__(
        self,
        state: Any,
        *,
        call: Any = None,
        result: Any = None,
        **kwargs: Any,
    ) -> ToolResult | None:
        """``after_tool_call`` hook: offload oversized results to disk.

        Returns the original *result* unchanged when the output is small or when
        ``is_error`` is ``True`` — errors must remain visible to the model.
        """
        if result is None:
            return None
        if result.is_error:
            return result
        if len(result.output) < self.config.threshold_chars:
            return result

        tool_name = call.name if call is not None else "unknown"
        filename = self.offload(tool_name=tool_name, content=result.output)
        preview = self._build_handle_message(filename, result.output)
        return ToolResult(output=preview, metadata={"offloaded_to": filename})
