"""Tests for provider registry."""
import pytest

from vulpcode.providers import (
    OPENAI_COMPATIBLE_PRESETS,
    Provider,
    build_provider,
    get_provider_class,
    list_provider_names,
)
from vulpcode.providers.anthropic import AnthropicProvider
from vulpcode.providers.gemini import GeminiProvider
from vulpcode.providers.ollama import OllamaProvider
from vulpcode.providers.openai import OpenAIProvider


def test_known_names_present():
    names = list_provider_names()
    for n in (
        "anthropic",
        "openai",
        "deepseek",
        "groq",
        "openrouter",
        "lmstudio",
        "vllm",
        "gemini",
        "ollama",
    ):
        assert n in names


def test_get_class_dedicated():
    assert get_provider_class("anthropic") is AnthropicProvider
    assert get_provider_class("gemini") is GeminiProvider
    assert get_provider_class("ollama") is OllamaProvider


def test_get_class_openai_family():
    assert get_provider_class("openai") is OpenAIProvider
    assert get_provider_class("deepseek") is OpenAIProvider
    assert get_provider_class("groq") is OpenAIProvider
    assert get_provider_class("openrouter") is OpenAIProvider
    assert get_provider_class("lmstudio") is OpenAIProvider
    assert get_provider_class("vllm") is OpenAIProvider


def test_unknown_raises():
    with pytest.raises(ValueError):
        get_provider_class("nope")


def test_case_insensitive_lookup():
    assert get_provider_class("Anthropic") is AnthropicProvider
    assert get_provider_class("DEEPSEEK") is OpenAIProvider


def test_build_anthropic():
    p = build_provider("anthropic", {"api_key": "x"})
    assert isinstance(p, AnthropicProvider)


def test_build_deepseek_uses_preset():
    p = build_provider("deepseek", {"api_key": "x"})
    assert isinstance(p, OpenAIProvider)
    assert p.base_url == OPENAI_COMPATIBLE_PRESETS["deepseek"]


def test_build_groq_uses_preset():
    p = build_provider("groq", {"api_key": "x"})
    assert isinstance(p, OpenAIProvider)
    assert p.base_url == OPENAI_COMPATIBLE_PRESETS["groq"]


def test_build_user_override_wins():
    p = build_provider("groq", {"api_key": "x", "base_url": "http://custom"})
    assert p.base_url == "http://custom"


def test_build_openai_no_preset():
    p = build_provider("openai", {"api_key": "x"})
    assert isinstance(p, OpenAIProvider)
    assert p.base_url is None


def test_build_ollama_default():
    p = build_provider("ollama")
    assert isinstance(p, OllamaProvider)
    assert "11434" in p.base_url


def test_returned_is_provider():
    p = build_provider("openai", {"api_key": "x"})
    assert isinstance(p, Provider)


def test_build_unknown_raises():
    with pytest.raises(ValueError):
        build_provider("nope")
