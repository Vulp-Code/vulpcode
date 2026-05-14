# Tarefa 07.01 - Sistema de Configuracao

**Status**: PENDENTE
**Fase**: 07 - Config + Permissoes
**Dependencias**: 02.01, 03.05 (registry de providers)
**Bloqueia**: FASE 08 (agent precisa do config), FASE 06.03 (Task usa config)

---

## Objetivo

Implementar `src/vulpcode/config.py` com carga hierarquica:
1. Defaults embutidos
2. `~/.vulpcode/config.toml` (global)
3. `.vulpcode/config.toml` no projeto (cwd ou ancestrais)
4. Variaveis de ambiente (`VULPCODE_*`, mais padrao `ANTHROPIC_API_KEY` etc.)
5. Flags da CLI

Cada nivel sobrescreve o anterior.

---

## Descricao Tecnica

### Funcoes publicas

```python
def load_config(
    *,
    cli_overrides: dict | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]: ...

def save_config(
    config: dict[str, Any],
    scope: Literal["global", "project"] = "global",
) -> Path: ...

def config_paths(cwd: Path | None = None) -> list[Path]:
    """Returns the discovery order of config.toml files."""
```

### Defaults

```python
DEFAULTS: dict[str, Any] = {
    "default_provider": "anthropic",
    "default_model": "",
    "providers": {},
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
```

### Variaveis de ambiente

Mapeamento explicito:

```python
ENV_MAP = {
    "VULPCODE_PROVIDER": ("default_provider",),
    "VULPCODE_MODEL": ("default_model",),
    "ANTHROPIC_API_KEY": ("providers", "anthropic", "api_key"),
    "OPENAI_API_KEY": ("providers", "openai", "api_key"),
    "GEMINI_API_KEY": ("providers", "gemini", "api_key"),
    "GOOGLE_API_KEY": ("providers", "gemini", "api_key"),
    "DEEPSEEK_API_KEY": ("providers", "deepseek", "api_key"),
    "GROQ_API_KEY": ("providers", "groq", "api_key"),
    "OPENROUTER_API_KEY": ("providers", "openrouter", "api_key"),
}
```

### Estrutura

**`src/vulpcode/config.py`**:

```python
"""Configuration loader with hierarchical precedence."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

import tomli_w


DEFAULTS: dict[str, Any] = {
    "default_provider": "anthropic",
    "default_model": "",
    "providers": {},
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
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge overlay into base; lists are replaced, not merged."""
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _set_path(d: dict, path: tuple[str, ...], value: Any) -> None:
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
    cwd = cwd or Path.cwd()
    env = env if env is not None else os.environ
    cfg = dict(DEFAULTS)
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
    cwd = cwd or Path.cwd()
    if scope == "global":
        target = Path.home() / ".vulpcode" / "config.toml"
    else:
        target = cwd / ".vulpcode" / "config.toml"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        tomli_w.dump(config, fh)
    return target
```

---

## INSTRUCAO CRITICA

- Usar `tomllib` (stdlib desde Python 3.11) para leitura, `tomli_w` para escrita.
- Procurar `.vulpcode/config.toml` em ancestrais — habito comum em VCS-rooted
  projects. Usuarios podem por config no root do repo.
- Nao mergear listas — sempre substituir. Comportamento mais previsivel.
- Variaveis de ambiente APENAS sobrescrevem se o valor estiver setado e nao-vazio.
- `cli_overrides` e o ultimo nivel: sempre vence.
- Default `default_model = ""` — se vazio, o agent loop pega o primeiro modelo
  retornado por `provider.list_models()` ou pede ao usuario.

---

## Etapas de Implementacao

### Etapa 1: Criar `config.py`

Conteudo conforme acima.

### Etapa 2: Criar `tests/test_config.py`

```python
import json
from pathlib import Path

import pytest

from vulpcode.config import (
    DEFAULTS,
    config_paths,
    load_config,
    save_config,
)


def test_defaults_loaded(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_config(cwd=tmp_path, env={})
    assert cfg["default_provider"] == "anthropic"
    assert cfg["permissions"]["auto_approve_read"] is True


def test_global_config_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".vulpcode").mkdir()
    (tmp_path / ".vulpcode" / "config.toml").write_text(
        'default_provider = "openai"\n'
        '[providers.openai]\napi_key = "abc"\n'
    )
    cfg = load_config(cwd=tmp_path, env={})
    assert cfg["default_provider"] == "openai"
    assert cfg["providers"]["openai"]["api_key"] == "abc"


def test_project_config_overrides_global(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "h"))
    home = tmp_path / "h"
    home.mkdir()
    (home / ".vulpcode").mkdir()
    (home / ".vulpcode" / "config.toml").write_text('default_provider = "openai"\n')

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".vulpcode").mkdir()
    (proj / ".vulpcode" / "config.toml").write_text('default_provider = "ollama"\n')

    cfg = load_config(cwd=proj, env={})
    assert cfg["default_provider"] == "ollama"


def test_env_var_overrides_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".vulpcode").mkdir()
    (tmp_path / ".vulpcode" / "config.toml").write_text('default_provider = "openai"\n')
    cfg = load_config(cwd=tmp_path, env={"VULPCODE_PROVIDER": "anthropic"})
    assert cfg["default_provider"] == "anthropic"


def test_anthropic_api_key_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_config(cwd=tmp_path, env={"ANTHROPIC_API_KEY": "sk-x"})
    assert cfg["providers"]["anthropic"]["api_key"] == "sk-x"


def test_cli_overrides_win(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_config(
        cwd=tmp_path, env={"VULPCODE_PROVIDER": "openai"},
        cli_overrides={"default_provider": "ollama"},
    )
    assert cfg["default_provider"] == "ollama"


def test_save_global(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = save_config({"default_provider": "openai"}, scope="global", cwd=tmp_path)
    assert target.exists()
    text = target.read_text()
    assert 'default_provider' in text


def test_config_paths_includes_global(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths = config_paths(cwd=tmp_path)
    assert any(".vulpcode" in str(p) for p in paths)
```

### Etapa 3: Rodar testes

```bash
pytest tests/test_config.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/config.py` criado com `load_config`, `save_config`, `config_paths`
- [x] Defaults carregados primeiro
- [x] `~/.vulpcode/config.toml` carregado se existir
- [x] `.vulpcode/config.toml` em cwd ou ancestrais sobrescreve global
- [x] Variaveis de ambiente sobrescrevem arquivos
- [x] `cli_overrides` (param) sobrescrevem todos
- [x] Listas sao substituidas (nao mergeadas)
- [x] `save_config(scope="global"|"project")` escreve o arquivo correto
- [x] `tests/test_config.py` com >=8 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| `tomllib` ausente em Python <3.11 | Alta | Alto | requires-python >=3.11 no pyproject |
| Encoding TOML | Baixa | Baixo | Sempre UTF-8 |
| Permissoes em ~/.vulpcode | Baixa | Medio | mkdir parents=True |

---

**End of Specification**
