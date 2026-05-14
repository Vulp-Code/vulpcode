# Tarefa 03.05 - Provider Registry e Factory

**Status**: PENDENTE
**Fase**: 03 - Providers
**Dependencias**: 03.01, 03.02, 03.03, 03.04
**Bloqueia**: FASE 07 (config carrega provider via registry), FASE 08 (agent recebe provider via registry)

---

## Objetivo

Criar `src/vulpcode/providers/registry.py` com lookup por nome (`"anthropic"`,
`"openai"`, `"deepseek"`, `"groq"`, `"openrouter"`, `"lmstudio"`, `"vllm"`,
`"gemini"`, `"ollama"`) e funcao `build_provider(name, config)` que monta o
provider correto com `base_url` apropriado.

---

## Descricao Tecnica

### Mapa de presets

`OpenAIProvider` cobre varios backends parametrizado por `base_url`. Centralizamos
isto em um dict de presets:

```python
OPENAI_COMPATIBLE_PRESETS: dict[str, str] = {
    "openai": "",  # default (None)
    "deepseek": "https://api.deepseek.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "lmstudio": "http://localhost:1234/v1",
    "vllm": "http://localhost:8000/v1",
}
```

### Funcoes do registry

```python
def list_provider_names() -> list[str]:
    """All known provider names (anthropic, openai, deepseek, ..., gemini, ollama)."""

def build_provider(name: str, config: dict[str, Any] | None = None) -> Provider:
    """Instantiate a provider by name with the given config dict.

    Config accepts: api_key, base_url, timeout, plus provider-specific extras.
    """

def get_provider_class(name: str) -> type[Provider]:
    """Return the underlying class for a given provider name."""
```

### Estrutura

**`src/vulpcode/providers/registry.py`**:

```python
"""Provider lookup and construction by name."""
from __future__ import annotations

from typing import Any

from vulpcode.providers.anthropic import AnthropicProvider
from vulpcode.providers.base import Provider
from vulpcode.providers.gemini import GeminiProvider
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


_DEDICATED: dict[str, type[Provider]] = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


def list_provider_names() -> list[str]:
    """All known provider names."""
    return sorted(set(_DEDICATED) | set(OPENAI_COMPATIBLE_PRESETS))


def get_provider_class(name: str) -> type[Provider]:
    if name in _DEDICATED:
        return _DEDICATED[name]
    if name in OPENAI_COMPATIBLE_PRESETS:
        return OpenAIProvider
    raise ValueError(f"Unknown provider: {name!r}. Known: {list_provider_names()}")


def build_provider(name: str, config: dict[str, Any] | None = None) -> Provider:
    """Build a Provider instance by name.

    Args:
        name: provider name (e.g. "anthropic", "deepseek", "ollama").
        config: dict with api_key, base_url, timeout, ... If base_url is omitted
            and the name is an OpenAI-compatible preset, the preset URL is used.
    """
    cfg = dict(config or {})
    cls = get_provider_class(name)

    if name in OPENAI_COMPATIBLE_PRESETS:
        preset = OPENAI_COMPATIBLE_PRESETS[name]
        if preset and not cfg.get("base_url"):
            cfg["base_url"] = preset

    instance = cls(**cfg)
    return instance
```

### Atualizar `providers/__init__.py`

Adicionar reexports:

```python
from vulpcode.providers.registry import (
    OPENAI_COMPATIBLE_PRESETS,
    build_provider,
    get_provider_class,
    list_provider_names,
)
```

E adicionar a `__all__`.

### Atualizar `cli.py` (subcomando `providers`)

Substituir a tabela hardcoded por `list_provider_names()`. Continue mostrando as
mesmas colunas.

---

## INSTRUCAO CRITICA

- `build_provider()` aceita config arbitraria via `**cfg` — mas todos os providers
  aceitam pelo menos `api_key`, `base_url`, `timeout`. Extras vao para `**extra`
  da subclass que os ignora se nao usar.
- Se o usuario passar `base_url` explicitamente em config, NAO sobrescrever com
  o preset — o preset e apenas default.
- O nome do provider que o usuario digita pode ser case-insensitive: a funcao
  pode normalizar com `.lower()`. Documentar isto no docstring.
- Nao registramos sub-aliases dinamicos no `_DEDICATED` — esses sao apenas
  Anthropic/Gemini/Ollama (que sao classes proprias). Tudo OpenAI-compativel
  passa pelo `OPENAI_COMPATIBLE_PRESETS`.

---

## Etapas de Implementacao

### Etapa 1: Criar `providers/registry.py`

Conteudo conforme acima.

### Etapa 2: Atualizar `providers/__init__.py`

Re-exportar `build_provider`, `get_provider_class`, `list_provider_names`,
`OPENAI_COMPATIBLE_PRESETS`.

### Etapa 3: Atualizar `cli.py` subcomando `providers`

```python
@app.command()
def providers() -> None:
    """List known providers."""
    from vulpcode.providers import list_provider_names, OPENAI_COMPATIBLE_PRESETS

    table = Table(title="Vulpcode providers")
    table.add_column("name", style="cyan")
    table.add_column("backend")
    for name in list_provider_names():
        if name in OPENAI_COMPATIBLE_PRESETS:
            backend = f"OpenAI-compatible ({OPENAI_COMPATIBLE_PRESETS[name] or 'default'})"
        else:
            backend = name.capitalize()
        table.add_row(name, backend)
    console.print(table)
```

### Etapa 4: Criar `tests/test_providers/test_registry.py`

```python
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
    for n in ("anthropic", "openai", "deepseek", "groq", "openrouter", "gemini", "ollama"):
        assert n in names


def test_get_class_dedicated():
    assert get_provider_class("anthropic") is AnthropicProvider
    assert get_provider_class("gemini") is GeminiProvider
    assert get_provider_class("ollama") is OllamaProvider


def test_get_class_openai_family():
    assert get_provider_class("openai") is OpenAIProvider
    assert get_provider_class("deepseek") is OpenAIProvider
    assert get_provider_class("groq") is OpenAIProvider


def test_unknown_raises():
    with pytest.raises(ValueError):
        get_provider_class("nope")


def test_build_anthropic():
    p = build_provider("anthropic", {"api_key": "x"})
    assert isinstance(p, AnthropicProvider)


def test_build_deepseek_uses_preset():
    p = build_provider("deepseek", {"api_key": "x"})
    assert isinstance(p, OpenAIProvider)
    assert p.base_url == OPENAI_COMPATIBLE_PRESETS["deepseek"]


def test_build_user_override_wins():
    p = build_provider("groq", {"api_key": "x", "base_url": "http://custom"})
    assert p.base_url == "http://custom"


def test_build_ollama_default():
    p = build_provider("ollama")
    assert isinstance(p, OllamaProvider)
    assert "11434" in p.base_url


def test_returned_is_provider():
    p = build_provider("openai", {"api_key": "x"})
    assert isinstance(p, Provider)
```

### Etapa 5: Rodar testes

```bash
pytest tests/test_providers/test_registry.py tests/test_cli_skeleton.py -v
```

Todos passam (incluindo o teste atualizado de providers no CLI).

---

## Criterios de Aceite

- [x] `src/vulpcode/providers/registry.py` criado com `build_provider`, `get_provider_class`, `list_provider_names`
- [x] `OPENAI_COMPATIBLE_PRESETS` define `openai`, `deepseek`, `groq`, `openrouter`, `lmstudio`, `vllm`
- [x] `_DEDICATED` mapeia `anthropic`, `gemini`, `ollama` para suas classes
- [x] `build_provider("deepseek", ...)` cria `OpenAIProvider` com `base_url` correto
- [x] `base_url` explicito do usuario sobrescreve o preset
- [x] `providers/__init__.py` re-exporta o registry
- [x] `cli.py` subcomando `providers` usa `list_provider_names()` (nao mais hardcoded)
- [x] `tests/test_providers/test_registry.py` com >=8 testes, todos passando
- [x] `vulp providers` continua funcionando (`pytest tests/test_cli_skeleton.py::test_providers_table` passa)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Imports circulares | Baixa | Medio | Registry importa providers, nao o contrario |
| Tabela do CLI muda formato e quebra testes | Media | Baixo | Verificar nomes essenciais, nao formatacao |

---

**End of Specification**
