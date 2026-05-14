# Setup de desenvolvimento

Este guia cobre tudo o que voce precisa para rodar Vulpcode a partir do
codigo-fonte: clone, ambiente virtual, dependencias, testes, linters, build
do site de documentacao e build do pacote.

Pre-requisitos:

- **Python 3.11+** (`python --version`)
- **git**
- **make** opcional (nao usado pelo projeto, mas util para scripts proprios)

## 1. Clone e ambiente virtual

```bash
git clone https://github.com/vulpcode/vulpcode.git
cd vulpcode
python -m venv .venv
source .venv/bin/activate         # Linux / macOS
# .venv\Scripts\activate          # Windows (PowerShell)
pip install --upgrade pip
pip install -e '.[dev,docs,search]'
```

A instalacao em modo editavel (`-e`) faz com que mudancas em `src/vulpcode/`
sejam refletidas imediatamente sem reinstalar.

Os tres extras instalam:

| Extra    | Pacotes                                                              |
|----------|----------------------------------------------------------------------|
| `dev`    | `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `respx`    |
| `docs`   | `mkdocs`, `mkdocs-material`, `mkdocstrings[python]`, `pymdown-extensions` |
| `search` | `duckduckgo-search` (necessario para a tool `WebSearch`)             |

As versoes minimas exatas estao em
[`pyproject.toml`](https://github.com/vulpcode/vulpcode/blob/main/pyproject.toml).

## 2. Verificar a instalacao

```bash
vulp --version             # vulpcode 0.1.0
vulp providers             # tabela com os providers suportados
pytest tests/ -q           # suite completa deve passar
```

Se `vulp --version` falhar com "command not found", confirme que o venv esta
ativo (`which vulp` deve apontar para `.venv/bin/vulp`).

## 3. Estrutura do repositorio

```
vulpcode/
|-- src/vulpcode/           # codigo do pacote
|   |-- providers/          # adapters Anthropic, OpenAI, Gemini, Ollama, ...
|   |-- tools/              # Read, Write, Edit, Bash, Grep, Glob, Agent, WebSearch, WebFetch
|   |-- ui/                 # render Rich (streaming, painel de tools, banner)
|   |-- commands/           # slash commands do REPL
|   |-- mcp/                # cliente e loader MCP
|   |-- agent.py            # loop agentic
|   |-- permissions.py      # politicas de permissao
|   |-- config.py           # leitura de config.toml e env
|   |-- session.py          # historico em jsonl
|   |-- cli.py              # entrypoint typer
|   `-- app.py              # bootstrap do REPL
|-- tests/                  # pytest
|   |-- test_providers/
|   |-- test_tools/
|   `-- test_*.py
|-- docs/                   # site mkdocs (este conteudo)
|-- dev/                    # planejamento (codigo + documentacao)
|-- CHANGELOG.md
|-- pyproject.toml
`-- README.md
```

## 4. Rodar testes

```bash
# Suite completa, verbosa
pytest tests/ -v

# Um modulo isolado
pytest tests/test_providers/test_anthropic.py -v

# Um teste especifico
pytest tests/test_agent.py::test_agent_simple_response -v

# Cobertura
pytest --cov=src/vulpcode --cov-report=term-missing tests/

# Apenas testes async
pytest tests/ -m asyncio -v
```

Configuracao do pytest em `pyproject.toml`:

- `asyncio_mode = "auto"` — todos os `async def test_*` rodam sem decorator.
- `testpaths = ["tests"]` — `pytest` sem argumentos roda a suite inteira.
- `addopts = ["-ra", "--strict-markers"]` — mostra resumo de skips/falhas e
  rejeita marcadores nao declarados.

## 5. Linters e formatters

```bash
# Lint (E, F, I, B, UP, ASYNC)
ruff check src/ tests/

# Formatador (4 espacos, line length 100)
ruff format src/ tests/

# Type check estrito
mypy src/vulpcode/
```

A configuracao do `ruff` e do `mypy` esta em `pyproject.toml`:

- `ruff` ignora `E501` (line-too-long) e usa `target-version = "py311"`.
- `mypy` roda em modo `strict` com `warn_unreachable = true`.

## 6. Build do site de documentacao

```bash
mkdocs serve              # http://localhost:8000 com auto-reload
mkdocs build --strict     # exige zero warnings; usado pelo CI
```

`--strict` faz com que qualquer link interno quebrado, anchor faltando ou
arquivo orfao falhe o build. Sempre teste local antes de abrir PR que altera
documentacao.

## 7. Build do pacote

```bash
pip install build
python -m build
ls dist/                  # vulpcode-0.1.0-py3-none-any.whl + .tar.gz
```

O artefato segue o layout `src/` declarado em
`[tool.hatch.build.targets.wheel]`.

## 8. Workflow de contribuicao

1. Faca um fork no GitHub.
2. Crie uma branch descritiva: `git checkout -b feat/minha-feature`.
3. Implemente o codigo + adicione testes em `tests/`.
4. `pytest tests/` deve passar.
5. `ruff check && ruff format` deve estar limpo.
6. `mypy src/vulpcode/` nao deve introduzir novos erros.
7. Atualize a documentacao se a mudanca for visivel ao usuario.
8. Commit com mensagem descritiva (veja [convencoes](code-conventions.md#commits)).
9. Abra o PR contra `main`.
10. O CI roda automaticamente em multiplas versoes do Python; aguarde verde
    antes de pedir review.

## Proximo passo

Leia as [convencoes de codigo](code-conventions.md) antes de mandar codigo
para revisao.
