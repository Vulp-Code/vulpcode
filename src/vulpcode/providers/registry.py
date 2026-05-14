"""Provider lookup and construction by name.

This is the single entry point the rest of the codebase uses to obtain a
configured :class:`~vulpcode.providers.base.Provider`. Two kinds of providers
are registered:

- **Dedicated** adapters (Anthropic, Gemini, Ollama, internal-llm) — each has
  its own class.
- **OpenAI-compatible** presets (OpenAI itself, DeepSeek, Groq, OpenRouter,
  LM Studio, vLLM) — all share :class:`~vulpcode.providers.openai.OpenAIProvider`,
  differing only in ``base_url``.

Adding a new dedicated provider means adding it to :data:`_DEDICATED`. Adding
an OpenAI-compatible provider means adding a preset URL to
:data:`OPENAI_COMPATIBLE_PRESETS`.
"""
from __future__ import annotations

from typing import Any

from vulpcode.providers.anthropic import AnthropicProvider
from vulpcode.providers.base import Provider
from vulpcode.providers.gemini import GeminiProvider
from vulpcode.providers.internal_llm import InternalLLMProvider
from vulpcode.providers.ollama import OllamaProvider
from vulpcode.providers.openai import OpenAIProvider


OPENAI_COMPATIBLE_PRESETS: dict[str, str | None] = {
    "openai": None,
    "deepseek": "https://api.deepseek.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "lmstudio": "http://localhost:1234/v1",
    "vllm": "http://localhost:8000/v1",
}
"""Mapping of OpenAI-compatible provider name to its default ``base_url``.

A value of ``None`` means "use the SDK default" (only ``"openai"`` itself).
Any explicit ``base_url`` passed in ``config`` always wins over the preset.
"""


_DEDICATED: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "internal-llm": InternalLLMProvider,
    "ollama": OllamaProvider,
}


def list_provider_names() -> list[str]:
    """List all known provider names.

    Returns:
        Sorted union of dedicated providers and OpenAI-compatible preset
        names. Useful for ``--help`` text and validation.

    Example:
        >>> list_provider_names()
        ['anthropic', 'deepseek', 'gemini', 'groq', 'internal-llm',
         'lmstudio', 'ollama', 'openai', 'openrouter', 'vllm']
    """
    return sorted(set(_DEDICATED) | set(OPENAI_COMPATIBLE_PRESETS))


def get_provider_class(name: str) -> type[Provider]:
    """Return the underlying class for a given provider name.

    The name lookup is case-insensitive. OpenAI-compatible presets all resolve
    to :class:`~vulpcode.providers.openai.OpenAIProvider`.

    Args:
        name: Provider name (e.g. ``"anthropic"``, ``"deepseek"``, ``"ollama"``).

    Returns:
        The :class:`Provider` subclass that handles this name.

    Raises:
        ValueError: If ``name`` is not a known provider.

    Example:
        >>> get_provider_class("anthropic").__name__
        'AnthropicProvider'
        >>> get_provider_class("deepseek").__name__
        'OpenAIProvider'
    """
    key = name.lower()
    if key in _DEDICATED:
        return _DEDICATED[key]
    if key in OPENAI_COMPATIBLE_PRESETS:
        return OpenAIProvider
    raise ValueError(f"Unknown provider: {name!r}. Known: {list_provider_names()}")


def build_provider(name: str, config: dict[str, Any] | None = None) -> Provider:
    """Build a configured :class:`Provider` instance by name.

    The name lookup is case-insensitive. For OpenAI-compatible presets, if the
    caller did not set ``base_url`` in ``config`` and the preset has one, it
    is filled in automatically. An explicit ``base_url`` always wins.

    Args:
        name: Provider name (e.g. ``"anthropic"``, ``"deepseek"``, ``"ollama"``).
        config: Configuration dict with keys like ``api_key``, ``base_url``,
            ``timeout``. May also include provider-specific extras (e.g.
            ``user_uuid`` for ``internal-llm``). ``None`` means "use defaults".

    Returns:
        A ready-to-use :class:`Provider` instance.

    Raises:
        ValueError: If ``name`` is not a known provider.

    Example:
        >>> p = build_provider("anthropic", {"api_key": "sk-ant-..."})
        >>> p.name
        'anthropic'
        >>> p = build_provider("deepseek", {"api_key": "sk-..."})
        >>> p.base_url
        'https://api.deepseek.com/v1'
    """
    cfg = dict(config or {})
    key = name.lower()
    cls = get_provider_class(key)

    if key in OPENAI_COMPATIBLE_PRESETS:
        preset = OPENAI_COMPATIBLE_PRESETS[key]
        if preset and not cfg.get("base_url"):
            cfg["base_url"] = preset

    return cls(**cfg)
