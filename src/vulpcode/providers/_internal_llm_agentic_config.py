"""User-editable JSON config for the ``internal-llm-agentic`` provider.

Lives at ``~/.vulpcode/internal-llm-agentic.json`` so users can adjust endpoint,
UUID and token budgets without touching the TOML hierarchy. On startup, if the
file is missing it is auto-created from a template and the caller is told to
edit it and restart.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "internal-llm-agentic.json"

TEMPLATE: dict[str, Any] = {
    "_README": (
        "Preencha 'endpoint' e 'user_uuid' e reinicie o vulpcode. "
        "Limites de tokens (max_input_tokens / max_output_tokens), timeout, "
        "temperatura e demais parâmetros ficam em .vulpcode/config.toml — "
        "eles variam por modelo e por projeto, então são editados lá."
    ),
    "endpoint": "",
    "user_uuid": "",
}

REQUIRED_FIELDS = ("endpoint", "user_uuid")


class ConfigCreated(RuntimeError):
    """Raised on first run: template was written, user must edit and restart."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(str(path))


class ConfigIncomplete(RuntimeError):
    """Raised when the file exists but required fields are blank/missing."""

    def __init__(self, path: Path, missing: list[str]) -> None:
        self.path = path
        self.missing = missing
        super().__init__(f"missing fields {missing} in {path}")


def config_path() -> Path:
    """Return the absolute path of the JSON config file."""
    return Path.home() / ".vulpcode" / CONFIG_FILENAME


def _write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(TEMPLATE, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def load_or_init(path: Path | None = None) -> dict[str, Any]:
    """Load the JSON config, or create a template and raise ``ConfigCreated``.

    Raises:
        ConfigCreated: When the file did not exist; the template was just
            written. The caller should print a "configure and restart" message.
        ConfigIncomplete: When the file exists but a required field is blank.

    Returns:
        The parsed config dict (with required fields present and non-empty).
    """
    target = path or config_path()
    if not target.exists():
        _write_template(target)
        raise ConfigCreated(target)

    with target.open("r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ConfigIncomplete(target, [f"<JSON inválido: {exc.msg}>"]) from exc

    if not isinstance(data, dict):
        raise ConfigIncomplete(target, ["<o JSON precisa ser um objeto>"])

    missing = [
        f for f in REQUIRED_FIELDS
        if not isinstance(data.get(f), str) or not data.get(f, "").strip()
    ]
    if missing:
        raise ConfigIncomplete(target, missing)

    return data


def split_config(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split JSON config into ``(provider_kwargs, model_settings)``.

    Only ``endpoint`` and ``user_uuid`` are read here — everything else
    (token limits, timeout, temperature) belongs in
    ``.vulpcode/config.toml`` under ``[providers."internal-llm-agentic"]``
    since those vary per model and per project.
    """
    provider_kwargs: dict[str, Any] = {
        "base_url": data["endpoint"],
        "user_uuid": data["user_uuid"],
    }
    return provider_kwargs, {}


def render_created_message(path: Path) -> str:
    return (
        f"\n[internal-llm-agentic] arquivo de configuração criado em:\n"
        f"  {path}\n\n"
        f"Preencha 'endpoint' e 'user_uuid' e reinicie o vulpcode.\n"
        f"Os demais parâmetros (max_input_tokens, max_output_tokens, "
        f"temperature, top_p, timeout) ficam em "
        f".vulpcode/config.toml sob [providers.\"internal-llm-agentic\"].\n"
    )


def render_incomplete_message(path: Path, missing: list[str]) -> str:
    return (
        f"\n[internal-llm-agentic] configuração incompleta em:\n"
        f"  {path}\n\n"
        f"Campo(s) ausentes ou em branco: {', '.join(missing)}\n"
        f"Edite o arquivo, preencha esses campos e reinicie o vulpcode.\n"
    )
