# Tarefa 01.02 - pyproject.toml + Metadata

**Status**: PENDENTE
**Fase**: 01 - Bootstrap
**Dependencias**: 01.01 (estrutura)
**Bloqueia**: 01.03 e qualquer instalacao

---

## Objetivo

Criar `pyproject.toml` configurando build com `hatchling`, dependencias do projeto,
entry points (`vulp` e `vulpcode`), classifiers, e configuracao de ferramentas
(`ruff`, `pytest`, `mypy`). Apos esta tarefa, `pip install -e .` deve funcionar.

---

## Descricao Tecnica

**Arquivo a criar**: `/home/guhaase/projetos/vulpcode/pyproject.toml`

Espelha a especificacao do projeto (secao 13 do `vulpcode-projeto.md`) mas com
ajustes para o estado atual do desenvolvimento — algumas dependencias podem ser
movidas para `[project.optional-dependencies]` se ainda nao forem necessarias.

**Conteudo do `pyproject.toml`**:

```toml
[build-system]
requires = ["hatchling>=1.21"]
build-backend = "hatchling.build"

[project]
name = "vulpcode"
version = "0.1.0"
description = "Terminal coding agent, multi-provider (Anthropic, OpenAI, Gemini, Ollama, ...)"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Vulpcode Authors" }]
keywords = ["ai", "cli", "coding-agent", "claude", "ollama", "llm", "agent"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development",
    "Topic :: Terminals",
]

dependencies = [
    "typer>=0.12",
    "rich>=13.7",
    "prompt_toolkit>=3.0",
    "httpx>=0.27",
    "pydantic>=2.5",
    "anthropic>=0.40",
    "openai>=1.50",
    "google-genai>=0.3",
    "ollama>=0.4",
    "tomli-w>=1.0",
    "mcp>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "mypy>=1.10",
]
search = [
    "duckduckgo-search>=6.0",
]

[project.scripts]
vulp = "vulpcode.cli:main"
vulpcode = "vulpcode.cli:main"

[project.urls]
Homepage = "https://github.com/vulpcode/vulpcode"
Repository = "https://github.com/vulpcode/vulpcode"
Issues = "https://github.com/vulpcode/vulpcode/issues"

# ━━━ HATCH ━━━
[tool.hatch.version]
path = "src/vulpcode/__init__.py"

[tool.hatch.build.targets.wheel]
packages = ["src/vulpcode"]

[tool.hatch.build.targets.sdist]
include = [
    "src/vulpcode",
    "README.md",
    "LICENSE",
    "pyproject.toml",
]

# ━━━ RUFF ━━━
[tool.ruff]
line-length = 100
target-version = "py311"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "B",   # bugbear
    "UP",  # pyupgrade
    "ASYNC",
]
ignore = ["E501"]  # line length handled by formatter

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["B011", "B017"]

# ━━━ PYTEST ━━━
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
python_files = ["test_*.py"]
addopts = ["-ra", "--strict-markers"]

# ━━━ MYPY ━━━
[tool.mypy]
python_version = "3.11"
strict = true
warn_unreachable = true
ignore_missing_imports = true
files = ["src/vulpcode"]
```

**Tambem criar arquivos auxiliares**:

`README.md` (placeholder minimo):
```markdown
# Vulpcode

Terminal coding agent, multi-provider. See `vulpcode-projeto.md` for spec.
```

`LICENSE` (MIT):
```
MIT License

Copyright (c) 2026 Vulpcode Authors

Permission is hereby granted, free of charge, to any person obtaining a copy
... (texto completo da MIT License)
```

`.gitignore`:
```
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
venv/
.coverage
htmlcov/
.vulpcode/
```

---

## INSTRUCAO CRITICA

- A versao `0.1.0` deve estar SOMENTE em `src/vulpcode/__init__.py` (`__version__ = "0.1.0"`).
  `pyproject.toml` aponta para esta string via `[tool.hatch.version] path = ...`.
  Isto evita versao duplicada.
- `[project.scripts]` cria os comandos `vulp` e `vulpcode` apontando para
  `vulpcode.cli:main`. Apos a tarefa 01.01 ja existe um stub `main()` — basta isso para
  `pip install -e .` validar.
- `asyncio_mode = "auto"` permite definir testes `async def` sem decorator.
- Use `license = { text = "MIT" }` (nao a forma SPDX `license = "MIT"`) para compatibilidade
  com versoes mais antigas de pip.

---

## Etapas de Implementacao

### Etapa 1: Criar `pyproject.toml`

Conteudo conforme especificado acima, em `/home/guhaase/projetos/vulpcode/pyproject.toml`.

### Etapa 2: Criar `README.md`

Placeholder minimo mencionado acima.

### Etapa 3: Criar `LICENSE`

Texto completo da MIT License com ano 2026 e detentor "Vulpcode Authors".

### Etapa 4: Criar `.gitignore`

Conforme conteudo acima.

### Etapa 5: Verificar instalavel

```bash
cd /home/guhaase/projetos/vulpcode
python -m pip install -e . 2>&1 | tail -20
```

Deve completar sem erro. Tambem:

```bash
python -c "import vulpcode; print(vulpcode.__version__)"
# Deve imprimir: 0.1.0
```

E o entry point:

```bash
which vulp
# Deve apontar para o venv
vulp 2>&1 || true
# Deve falhar com NotImplementedError (esperado — sera implementado em 01.03)
```

---

## Criterios de Aceite

- [x] `pyproject.toml` valido na raiz com build-backend hatchling
- [x] `README.md` placeholder criado
- [x] `LICENSE` MIT criado
- [x] `.gitignore` criado com entradas Python padrao
- [x] `pip install -e .` instala sem erros (executar e verificar saida)
- [x] `python -c "import vulpcode; print(vulpcode.__version__)"` imprime `0.1.0`
- [x] Comando `vulp` registrado no PATH (apenas existe — falhar com NotImplementedError e esperado nesta fase)
- [x] Versao definida apenas em `__init__.py` (hatch aponta para la)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Hatchling nao encontra version path | Media | Medio | `__init__.py` precisa de `__version__ = "..."` exato |
| Conflito de dependencias | Baixa | Medio | Versoes minimas conservadoras |
| Falta de README na build sdist | Baixa | Baixo | README placeholder garante presenca |

---

**End of Specification**
