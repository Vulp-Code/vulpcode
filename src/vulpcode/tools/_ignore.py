"""Shared ignore-filtering utility used by Glob, Grep (Python fallback) and Tree.

The goal is to keep the agent out of "noise" directories (``node_modules``,
``__pycache__``, ``.venv``, ``dist``, ...) so that a project-analysis flow
doesn't choke on tens of thousands of irrelevant paths.

Two layers stack:

1. A **hardcoded default list** covering the heavy-hitters across ecosystems
   (Python, Node, Rust, Go, Java, Terraform, build outputs, IDE caches). This
   always applies unless the caller opts out.

2. The repo's **.gitignore** (when present, looked up by walking up from the
   target path until a ``.git`` directory or filesystem root is found). Parsed
   with ``pathspec`` using ``gitignore`` so semantics match real git.

Public API:

- :func:`should_ignore(path, base, extra_patterns=None) -> bool` — quick check
  for a single absolute path.
- :func:`build_matcher(base, extra_patterns=None, use_gitignore=True, use_defaults=True)`
  — build a callable for use inside hot loops (saves re-loading gitignore).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable

import pathspec


DEFAULT_IGNORE_PATTERNS: tuple[str, ...] = (
    # Version control
    ".git/",
    ".hg/",
    ".svn/",
    # Python
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".venv/",
    "venv/",
    "env/",
    ".env/",
    "*.egg-info/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".tox/",
    ".coverage",
    "htmlcov/",
    # Node / JS
    "node_modules/",
    ".next/",
    ".nuxt/",
    ".turbo/",
    ".parcel-cache/",
    ".cache/",
    # Build outputs (multi-lang)
    "dist/",
    "build/",
    "out/",
    "target/",
    # Rust
    "Cargo.lock",
    # Go
    "vendor/",
    # Java / JVM
    ".gradle/",
    ".idea/",
    # Terraform
    ".terraform/",
    "*.tfstate",
    "*.tfstate.backup",
    # IDE / editor
    ".vscode/",
    ".vs/",
    "*.swp",
    "*.swo",
    "*~",
    # OS
    ".DS_Store",
    "Thumbs.db",
    # Coverage / logs
    "coverage/",
    "*.log",
)
"""Default ignore patterns applied unless ``use_defaults=False``.

Patterns follow gitignore syntax: a trailing ``/`` matches directories only,
a leading ``/`` anchors to ``base``. Patterns without slashes match anywhere.
"""


@dataclass(frozen=True)
class IgnoreMatcher:
    """A compiled matcher that decides whether a path should be ignored.

    Build via :func:`build_matcher`. Cheap to call in a tight loop — both
    pathspec instances and the resolved ``base`` are cached.
    """

    base: Path
    spec_defaults: pathspec.PathSpec | None
    spec_gitignore: pathspec.PathSpec | None
    spec_extra: pathspec.PathSpec | None

    def __call__(self, path: Path) -> bool:
        """Return True if ``path`` should be ignored.

        Args:
            path: Path to test. May be absolute or relative; gets resolved
                against ``base`` for matching.
        """
        try:
            rel = path.resolve().relative_to(self.base)
        except (ValueError, OSError):
            # Path lives outside base — leave it alone.
            return False
        rel_posix = rel.as_posix()
        # pathspec matches directories when the path string ends with "/".
        if path.is_dir() and not rel_posix.endswith("/"):
            rel_posix += "/"
        for spec in (self.spec_defaults, self.spec_gitignore, self.spec_extra):
            if spec is not None and spec.match_file(rel_posix):
                return True
        return False


def _find_gitignore(start: Path) -> Path | None:
    """Walk up from ``start`` looking for a sibling ``.gitignore`` of a ``.git`` dir."""
    cur = start if start.is_dir() else start.parent
    for parent in (cur, *cur.parents):
        if (parent / ".git").exists():
            gi = parent / ".gitignore"
            return gi if gi.is_file() else None
    return None


@lru_cache(maxsize=64)
def _load_spec_cached(text: str | None) -> pathspec.PathSpec | None:
    if not text:
        return None
    return pathspec.PathSpec.from_lines("gitignore", text.splitlines())


def _load_gitignore_spec(base: Path) -> pathspec.PathSpec | None:
    gi = _find_gitignore(base)
    if gi is None:
        return None
    try:
        text = gi.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return _load_spec_cached(text)


def build_matcher(
    base: Path | str,
    *,
    extra_patterns: Iterable[str] | None = None,
    use_gitignore: bool = True,
    use_defaults: bool = True,
) -> IgnoreMatcher:
    """Build a reusable :class:`IgnoreMatcher` rooted at ``base``.

    Args:
        base: Directory to anchor matching against (paths get resolved relative
            to this).
        extra_patterns: Caller-supplied additional patterns (gitignore syntax).
        use_gitignore: Whether to look for and apply a ``.gitignore`` from the
            enclosing git repo (walking up from ``base``).
        use_defaults: Whether to apply :data:`DEFAULT_IGNORE_PATTERNS`.

    Returns:
        A matcher callable that returns ``True`` for paths to ignore.
    """
    base_path = Path(base).expanduser().resolve()
    spec_defaults = (
        pathspec.PathSpec.from_lines("gitignore", DEFAULT_IGNORE_PATTERNS)
        if use_defaults
        else None
    )
    spec_gitignore = _load_gitignore_spec(base_path) if use_gitignore else None
    spec_extra = (
        pathspec.PathSpec.from_lines("gitignore", list(extra_patterns))
        if extra_patterns
        else None
    )
    return IgnoreMatcher(
        base=base_path,
        spec_defaults=spec_defaults,
        spec_gitignore=spec_gitignore,
        spec_extra=spec_extra,
    )


def should_ignore(
    path: Path | str,
    base: Path | str,
    *,
    extra_patterns: Iterable[str] | None = None,
    use_gitignore: bool = True,
    use_defaults: bool = True,
) -> bool:
    """One-shot convenience wrapper around :func:`build_matcher`."""
    matcher = build_matcher(
        base,
        extra_patterns=extra_patterns,
        use_gitignore=use_gitignore,
        use_defaults=use_defaults,
    )
    return matcher(Path(path))


def filter_paths(
    paths: Iterable[Path],
    matcher: IgnoreMatcher | Callable[[Path], bool],
) -> list[Path]:
    """Filter an iterable of paths, dropping those matched by ``matcher``."""
    return [p for p in paths if not matcher(p)]
