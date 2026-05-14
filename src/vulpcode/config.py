"""Configuration loader with hierarchical precedence."""
from __future__ import annotations

import copy
import os
import tomllib
from pathlib import Path
from typing import Any, Literal

import tomli_w

DEFAULTS: dict[str, Any] = {
    "default_provider": "anthropic",
    "default_model": "",
    "providers": {},
    "model_settings": {
        "max_tokens": 16384,
    },
    "ui": {"theme": "monokai", "show_token_usage": True},
    "permissions": {
        "auto_approve_read": True,
        "auto_approve_glob": True,
        "auto_approve_grep": True,
        "require_confirm_bash": True,
        "require_confirm_write": True,
        "require_confirm_edit": True,
        "always_allow_tools": [],
    },
    "mcp": {"servers": []},
}
"""Built-in defaults applied before any TOML file or env var.

This dict is the lowest layer of the config hierarchy used by
[`load_config`][vulpcode.config.load_config]. Every key here defines the
expected shape of the final config: TOML files, env vars and CLI overrides
can only *replace* values inside this skeleton (see `_deep_merge`).
"""


ENV_MAP: dict[str, tuple[str, ...]] = {
    "VULPCODE_PROVIDER": ("default_provider",),
    "VULPCODE_MODEL": ("default_model",),
    "ANTHROPIC_API_KEY": ("providers", "anthropic", "api_key"),
    "OPENAI_API_KEY": ("providers", "openai", "api_key"),
    "GEMINI_API_KEY": ("providers", "gemini", "api_key"),
    "GOOGLE_API_KEY": ("providers", "gemini", "api_key"),
    "DEEPSEEK_API_KEY": ("providers", "deepseek", "api_key"),
    "GROQ_API_KEY": ("providers", "groq", "api_key"),
    "OPENROUTER_API_KEY": ("providers", "openrouter", "api_key"),
    "INTERNAL_LLM_ENDPOINT": ("providers", "internal-llm", "base_url"),
    "INTERNAL_LLM_USER_UUID": ("providers", "internal-llm", "user_uuid"),
}
"""Mapping of environment variable name to its dotted path inside the config.

Each tuple is the sequence of nested keys to write into. For example,
``ANTHROPIC_API_KEY`` writes to ``cfg["providers"]["anthropic"]["api_key"]``.
Only env vars listed here are honored; everything else is ignored.
"""


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into base; lists are replaced, not merged."""
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _set_path(d: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cursor = d
    for key in path[:-1]:
        cursor = cursor.setdefault(key, {})
    cursor[path[-1]] = value


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _project_config_path(cwd: Path) -> Path | None:
    p = cwd.resolve()
    for d in [p, *p.parents]:
        cand = d / ".vulpcode" / "config.toml"
        if cand.exists():
            return cand
    return None


def config_paths(cwd: Path | None = None) -> list[Path]:
    """Return the discovery order of ``config.toml`` files.

    The search walks ``cwd`` and its parents looking for the closest
    ``.vulpcode/config.toml``; the global file is always included first.

    Args:
        cwd: Working directory to start the project search from. Defaults to
            the process current directory.

    Returns:
        Paths in load order — global first, then project (if found). Files
        that do not exist on disk are still returned so callers can surface
        them in messages like ``vulpcode --print-config``.
    """
    cwd = cwd or Path.cwd()
    paths: list[Path] = [Path.home() / ".vulpcode" / "config.toml"]
    proj = _project_config_path(cwd)
    if proj is not None:
        paths.append(proj)
    return paths


def load_config(
    *,
    cli_overrides: dict[str, Any] | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Load configuration with hierarchical precedence.

    Layers are deep-merged in order; later layers override earlier ones.
    Lists are *replaced* (not concatenated) by deeper layers.

    Args:
        cli_overrides: Dict whose values win over every other source.
            Useful for ``--provider`` / ``--model`` CLI flags.
        cwd: Directory to start the project-config search from. Defaults
            to ``Path.cwd()``.
        env: Mapping used for env-var lookups. Defaults to ``os.environ``;
            pass ``{}`` in tests to ignore the host environment.

    Returns:
        The fully resolved config dict.

    Order (later overrides earlier):
        1. [`DEFAULTS`][vulpcode.config.DEFAULTS]
        2. ``~/.vulpcode/config.toml`` (global)
        3. ``.vulpcode/config.toml`` in cwd or any ancestor (project)
        4. Environment variables ([`ENV_MAP`][vulpcode.config.ENV_MAP])
        5. ``cli_overrides`` (last word)
    """
    cwd = cwd or Path.cwd()
    env = env if env is not None else dict(os.environ)
    cfg: dict[str, Any] = copy.deepcopy(DEFAULTS)
    for path in config_paths(cwd):
        cfg = _deep_merge(cfg, _load_toml(path))

    for env_key, target_path in ENV_MAP.items():
        val = env.get(env_key)
        if val:
            _set_path(cfg, target_path, val)

    if cli_overrides:
        cfg = _deep_merge(cfg, cli_overrides)

    return cfg


def save_config(
    config: dict[str, Any],
    scope: Literal["global", "project"] = "global",
    cwd: Path | None = None,
) -> Path:
    """Persist a config dict as TOML.

    The parent directory is created if missing. The file is written with
    ``tomli_w.dump`` so the result round-trips through
    [`load_config`][vulpcode.config.load_config].

    Args:
        config: The dict to serialize. Typically the value returned by
            ``load_config(...)`` after in-memory edits.
        scope: ``"global"`` writes to ``~/.vulpcode/config.toml``;
            ``"project"`` writes to ``<cwd>/.vulpcode/config.toml``.
        cwd: Used only when ``scope == "project"``. Defaults to ``Path.cwd()``.

    Returns:
        The absolute path of the file that was written.
    """
    cwd = cwd or Path.cwd()
    if scope == "global":
        target = Path.home() / ".vulpcode" / "config.toml"
    else:
        target = cwd / ".vulpcode" / "config.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        tomli_w.dump(config, fh)
    return target
