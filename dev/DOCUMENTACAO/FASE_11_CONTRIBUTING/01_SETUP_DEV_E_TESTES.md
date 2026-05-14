# Tarefa 11.01 - Contributing: Setup Dev + Testes

**Status**: PENDENTE
**Fase**: 11 - Contributing
**Dependencias**: 10.02
**Bloqueia**: 11.02

---

## Objetivo

Criar `contributing/index.md`, `contributing/dev-setup.md`,
`contributing/code-conventions.md` documentando como rodar/testar o projeto.

---

## Arquivos a criar

- `docs/contributing/index.md`
- `docs/contributing/dev-setup.md`
- `docs/contributing/code-conventions.md`

---

## Source de verdade

- `pyproject.toml` — `dev` extras, configuracao do ruff/pytest/mypy
- `tests/` — estrutura
- `dev/` — planejamento original

---

## Conteudo de `contributing/index.md`

```markdown
# Contributing

Vulpcode e MIT, contribuicoes sao bem-vindas.

## Roteiro

1. [Setup de desenvolvimento](dev-setup.md) — clone, venv, deps, rodar testes
2. [Convencoes de codigo](code-conventions.md) — formato, type hints, docstrings
3. [Adicionando provider](add-provider.md) — passos para suportar novo modelo  # 11.02
4. [Adicionando tool](add-tool.md) — passos para criar nova tool                # 11.02

## Code of conduct

Contributors Covenant. Seja respeitoso. Discussoes tecnicas focadas no merito.
```

---

## Conteudo de `contributing/dev-setup.md`

### 1. Clone e venv

```bash
git clone https://github.com/vulpcode/vulpcode.git
cd vulpcode
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,docs,search]'
```

### 2. Verificar instalacao

```bash
vulp --version             # vulpcode 0.1.0
vulp providers             # tabela de 10 providers
pytest tests/ -q           # 325+ testes passam
```

### 3. Estrutura do repo

```
vulpcode/
├── src/vulpcode/           # codigo
│   ├── providers/
│   ├── tools/
│   ├── ui/
│   ├── commands/
│   ├── mcp/
│   ├── agent.py
│   ├── permissions.py
│   ├── config.py
│   ├── session.py
│   ├── cli.py
│   └── app.py
├── tests/                  # pytest
│   ├── test_providers/
│   ├── test_tools/
│   └── test_*.py
├── docs/                   # mkdocs (este site)
├── dev/                    # planejamento (codigo + docs)
└── pyproject.toml
```

### 4. Rodar testes

```bash
# Suite completa
pytest tests/ -v

# Um modulo
pytest tests/test_providers/test_anthropic.py -v

# Com cobertura
pytest --cov=src/vulpcode --cov-report=term-missing tests/

# Apenas async
pytest tests/ -m asyncio -v
```

### 5. Linters e formatters

```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/vulpcode/
```

### 6. Build do site doc

```bash
mkdocs serve              # localhost:8000
mkdocs build --strict     # exige zero warnings
```

### 7. Build do pacote

```bash
pip install build
python -m build
ls dist/                  # vulpcode-0.1.0-py3-none-any.whl + .tar.gz
```

### 8. Workflow de contribuicao

1. Fork no GitHub.
2. Crie uma branch: `git checkout -b feat/minha-feature`.
3. Mude codigo + adicione testes.
4. `pytest tests/` deve passar.
5. `ruff check && ruff format` deve estar limpo.
6. Commit com mensagem descritiva.
7. Abra PR contra `main`.
8. CI roda automatico (testes em multiple Python versions).

---

## Conteudo de `contributing/code-conventions.md`

### Geral

- **Python 3.11+** (usar `str | None`, nao `Optional[str]`)
- **Type hints obrigatorios** em funcoes publicas
- **Async** padrao: `asyncio` para I/O
- **Pydantic v2** para schemas

### Formatacao

- `ruff format` — auto-format (4 espacos, line length 100)
- `ruff check` — lint (rules: E, F, I, B, UP, ASYNC)

### Docstrings

Estilo **Google** (compatible com mkdocstrings):

```python
def build_provider(name: str, config: dict | None = None) -> Provider:
    """Build a provider instance by name.

    Args:
        name: Provider name (e.g. "anthropic").
        config: Configuration dict.

    Returns:
        A configured provider.

    Raises:
        ValueError: If name is not known.

    Example:
        >>> p = build_provider("anthropic", {"api_key": "sk-..."})
    """
```

### Imports

Ordem (ruff/isort cuida):
1. stdlib
2. third-party
3. local (`vulpcode.*`)

### Comentarios

Apenas onde o WHY nao e obvio. Comentarios que descrevem o que o codigo faz
sao desnecessarios — codigo bem nomeado ja diz.

### Naming

- Modulos: `snake_case`
- Classes: `PascalCase`
- Funcoes/metodos: `snake_case`
- Constantes: `UPPER_SNAKE_CASE`
- Privados: `_underscore_prefix`
- Tools: `PascalCase` no nome do registro (`Read`, `Write`, `BashOutput`)

### Testes

- pytest fixtures preferidos a setUp/tearDown
- `pytest-asyncio` para tests async (`asyncio_mode = "auto"` em pyproject)
- Mockar SDKs externos com `unittest.mock.patch` ou `respx` para httpx
- Cobertura alvo: 70%+ no codigo critico (providers, tools, agent)

### Commits

- Mensagens em portugues OK
- Imperativo: "adiciona", "corrige", "remove"
- Primeira linha < 72 chars
- Body com contexto se necessario

### Idioma

- **Codigo, comentarios em codigo, docstrings**: ingles
- **Documentacao do site (docs/)**: portugues
- **Mensagens de commit/PR**: portugues OK

---

## Atualizar `mkdocs.yml`

Adicionar bloco `Contributing`:

```yaml
- Contributing:
    - contributing/index.md
    - Setup de desenvolvimento: contributing/dev-setup.md
    - Convencoes de codigo: contributing/code-conventions.md
    - Adicionar provider: contributing/add-provider.md   # 11.02
    - Adicionar tool: contributing/add-tool.md           # 11.02
```

---

## INSTRUCAO CRITICA

- Confirmar que pyproject.toml tem `[project.optional-dependencies].dev` com
  pytest, pytest-asyncio, ruff, mypy. Listar os exatos.
- A estrutura do repo deve refletir o atual — verifique com `ls`.

---

## Etapas de Implementacao

### Etapa 1: Confirmar estrutura e pyproject
### Etapa 2: Criar 3 arquivos
### Etapa 3: Atualizar `mkdocs.yml`
### Etapa 4: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/contributing/index.md` criado com roteiro
- [x] `docs/contributing/dev-setup.md` cobre clone, venv, deps, testes, lint, build doc, build pacote, workflow
- [x] `docs/contributing/code-conventions.md` cobre Python version, type hints, docstrings (Google), imports, naming, testes, commits, idioma
- [x] `mkdocs.yml` atualizado com bloco Contributing
- [x] `mkdocs build` continua passando

---

**End of Specification**
