"""Centralized safety checks for write/edit/bash tools.

Provides:
- ``check_path_sandbox``: refuse writes outside the project, into system paths,
  sensitive HOME subdirs (``.ssh``, ``.aws``), or build/cache dirs (``.git``,
  ``.venv``, ``dist``, ...). Override with ``VULPCODE_ALLOW_UNSAFE_PATHS=1``.
- ``scan_secrets`` / ``format_secret_error``: regex-based detection of common
  credential patterns (AWS, GitHub, OpenAI, Anthropic, private keys, ...).
  Bypass per-file by embedding the marker ``vulpcode:allow-secret``.
- ``git_dirty``: detect uncommitted local changes on a file the writer is
  about to overwrite (used for warnings, never to block).
- ``classify_command``: rate-limit dangerous bash commands (rm -rf /, dd to
  raw disk, fork bombs, force-pushes, curl|sh, ...). Catastrophic patterns
  are blocked; risky ones return a warning the caller can surface.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


# ── path sandbox ────────────────────────────────────────────────────────────

_DENIED_SYSTEM_PREFIXES = (
    "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64",
    "/boot", "/sys", "/proc", "/dev", "/root",
)

_DENIED_HOME_SUBPATHS = (
    ".ssh", ".aws", ".gnupg", ".kube", ".docker",
)

_DENIED_PROJECT_DIRS = (
    ".git", ".venv", "venv", ".tox", "dist", "build", "site",
    "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache",
    ".pytest_cache",
)


def _project_root(start: Path) -> Path | None:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    for p in [cur, *cur.parents]:
        if (p / "pyproject.toml").exists() or (p / ".git").exists():
            return p
    return None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def check_path_sandbox(file_path: str | os.PathLike) -> str | None:
    """Return an error string if ``file_path`` is denied, else None.

    Allowed:
        * Anything inside the OS temp dir (so tmp_path-based tests pass).
        * Anything inside the detected project root, EXCEPT blocked subdirs.

    Denied:
        * System paths (/etc, /usr, /dev, ...).
        * Sensitive HOME subdirs (.ssh, .aws, .gnupg, .kube, .docker).
        * Cache/build subdirs within the project (.git, .venv, dist, build,
          site, node_modules, __pycache__, ...).

    Override: set ``VULPCODE_ALLOW_UNSAFE_PATHS=1`` to skip all checks.
    """
    if os.environ.get("VULPCODE_ALLOW_UNSAFE_PATHS") == "1":
        return None
    p = Path(file_path).expanduser().resolve()

    try:
        p.relative_to(Path(tempfile.gettempdir()).resolve())
        return None
    except ValueError:
        pass

    p_str = str(p)
    for pref in _DENIED_SYSTEM_PREFIXES:
        if p_str == pref or p_str.startswith(pref + "/"):
            return f"Path denied by sandbox (system path): {p}"

    home = Path.home().resolve()
    if _is_within(p, home):
        try:
            rel = p.relative_to(home)
            first = rel.parts[0] if rel.parts else ""
            if first in _DENIED_HOME_SUBPATHS:
                return f"Path denied by sandbox (sensitive HOME subdir): {p}"
        except ValueError:
            pass

    root = _project_root(p)
    if root is not None and _is_within(p, root):
        rel = p.resolve().relative_to(root.resolve())
        for blocked in _DENIED_PROJECT_DIRS:
            if rel.parts and rel.parts[0] == blocked:
                return (
                    f"Path denied by sandbox ({blocked}/ inside project): {p}. "
                    f"Set VULPCODE_ALLOW_UNSAFE_PATHS=1 to override."
                )

    return None


# ── secret detection ───────────────────────────────────────────────────────

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("AWS session key", re.compile(r"\bASIA[0-9A-Z]{16}\b")),
    ("GitHub PAT (classic)", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("GitHub PAT (fine-grained)", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b")),
    ("GitHub OAuth", re.compile(r"\bgho_[A-Za-z0-9]{36}\b")),
    ("OpenAI key", re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{40,}\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("Stripe live key", re.compile(r"\bsk_live_[0-9A-Za-z]{24,}\b")),
    ("Private key block", re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY(?: BLOCK)?-----"
    )),
)

_SECRET_ALLOW_MARKER = "vulpcode:allow-secret"


@dataclass
class SecretHit:
    label: str
    line: int
    sample: str


def scan_secrets(content: str) -> list[SecretHit]:
    """Scan ``content`` for known credential patterns.

    Returns an empty list if the bypass marker ``vulpcode:allow-secret`` is
    present anywhere in the content (intended for test fixtures that hold
    deliberately fake-but-realistic credentials).
    """
    if not isinstance(content, str) or _SECRET_ALLOW_MARKER in content:
        return []
    hits: list[SecretHit] = []
    for label, pat in _SECRET_PATTERNS:
        for m in pat.finditer(content):
            line = content.count("\n", 0, m.start()) + 1
            raw = m.group(0)
            sample = raw[:4] + "…" + raw[-2:] if len(raw) > 8 else "***"
            hits.append(SecretHit(label=label, line=line, sample=sample))
    return hits


def format_secret_error(hits: list[SecretHit]) -> str:
    lines = ["Secret(s) detected in content — refusing to write:"]
    for h in hits:
        lines.append(f"  - {h.label} at line {h.line}: {h.sample}")
    lines.append(
        f"\nIf this is intentional (test fixture, documentation example, ...), "
        f"add the marker `{_SECRET_ALLOW_MARKER}` anywhere in the file content."
    )
    return "\n".join(lines)


# ── git dirty check ─────────────────────────────────────────────────────────

def git_dirty(file_path: str | os.PathLike) -> bool:
    """True if ``file_path`` exists, is tracked by git, and has local changes.

    Returns False on any failure (no git, not in a repo, etc.) — this is a
    best-effort warning signal, never a hard gate.
    """
    p = Path(file_path).expanduser().resolve()
    if not p.exists():
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", str(p.parent), "status", "--porcelain", "--", p.name],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return proc.returncode == 0 and bool(proc.stdout.strip())


# ── bash command guard ─────────────────────────────────────────────────────

@dataclass
class CommandRisk:
    level: str  # "catastrophic" | "risky"
    reason: str


_CATASTROPHIC_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\brm\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/(?:\s|$|\*)"),
     "rm -rf at filesystem root"),
    (re.compile(r"\brm\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s+/(?:\s|$|\*)"),
     "rm -fr at filesystem root"),
    (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+\$HOME(?:\s|$|/)"),
     "rm -rf $HOME"),
    (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+~(?:\s|/|$)"),
     "rm -rf ~"),
    (re.compile(r"\bdd\b[^|]*\bof=/dev/(?:sd[a-z]|nvme\d|hd[a-z]|mmcblk\d)"),
     "dd writing to raw disk device"),
    (re.compile(r"\bmkfs(?:\.\w+)?\s+/dev/(?:sd[a-z]|nvme\d|hd[a-z])"),
     "mkfs on raw disk device"),
    (re.compile(r">\s*/dev/(?:sd[a-z]|nvme\d|hd[a-z])"),
     "redirect to raw disk device"),
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),
     "fork bomb"),
    (re.compile(r"\bchmod\s+-R\s+0*777\s+/(?:\s|$)"),
     "chmod -R 777 /"),
    (re.compile(r"\bshred\s+(?:-[a-zA-Z]+\s+)*/dev/(?:sd[a-z]|nvme\d|hd[a-z])"),
     "shred on raw disk"),
)

_RISKY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bgit\s+push\s+(?:[^;|&]*\s+)?(?:--force|-f)\b[^;|&]*\b(?:main|master)\b"),
     "force push to main/master"),
    (re.compile(r"\bgit\s+push\s+(?:[^;|&]*\s+)?\b(?:main|master)\b[^;|&]*(?:--force|-f)\b"),
     "force push to main/master"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"),
     "git reset --hard discards working tree changes"),
    (re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*f"),
     "git clean -f removes untracked files"),
    (re.compile(r"\b(?:curl|wget)\b[^|;&]*\|\s*(?:bash|sh|zsh)\b"),
     "piping remote content directly to a shell"),
    (re.compile(r"\bsudo\s+rm\s+-[a-zA-Z]*r"),
     "sudo rm -r"),
    (re.compile(r"--no-verify\b"),
     "skipping git hooks (--no-verify)"),
    (re.compile(r"\bgit\s+commit\b[^;|&]*--amend\b"),
     "amending a commit (rewrites history)"),
)


def classify_command(command: str) -> CommandRisk | None:
    """Return a :class:`CommandRisk` if ``command`` matches a known pattern.

    Catastrophic patterns should be blocked by the caller; risky patterns
    should be surfaced as a warning but allowed to proceed (the user already
    confirmed the call).
    """
    for pat, reason in _CATASTROPHIC_PATTERNS:
        if pat.search(command):
            return CommandRisk(level="catastrophic", reason=reason)
    for pat, reason in _RISKY_PATTERNS:
        if pat.search(command):
            return CommandRisk(level="risky", reason=reason)
    return None
