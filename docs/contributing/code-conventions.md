# Convencoes de codigo

Estas convencoes sao aplicadas no codigo dentro de `src/vulpcode/` e em
`tests/`. PRs que destoam delas serao pedidos para ajustar antes do merge.

## Geral

- **Python 3.11+**. Use sintaxe moderna: `str | None` (nao `Optional[str]`),
  `list[int]` (nao `List[int]`), `match` quando ajudar legibilidade.
- **Type hints obrigatorios** em toda funcao publica e em metodos de classes
  publicas.
- **Async por padrao** para I/O. Providers, tools de rede e o agent loop
  rodam em `asyncio`.
- **Pydantic v2** para schemas declarativos (config, mensagens, params de tool).

## Formatacao

`ruff format` cuida de toda formatacao. Nao discuta estilo em review — rode
o formatter.

- Indent: 4 espacos
- Line length: 100
- Quotes: padrao do ruff (double)

```bash
ruff format src/ tests/
```

## Lint

Regras ativas no `[tool.ruff.lint]`:

| Codigo  | O que pega                                  |
|---------|---------------------------------------------|
| `E`     | erros de estilo PEP 8                       |
| `F`     | erros logicos do pyflakes                   |
| `I`     | ordem de imports                            |
| `B`     | bugbear (bugs comuns)                       |
| `UP`    | pyupgrade (sintaxe moderna)                 |
| `ASYNC` | armadilhas de async (sleep sincrono, etc.)  |

`E501` (line too long) esta ignorado — o formatter quebra o que vale a pena
quebrar; o resto e prosa em string.

```bash
ruff check src/ tests/
```

## Type check

```bash
mypy src/vulpcode/
```

Configuracao em `[tool.mypy]`:

- `strict = true`
- `warn_unreachable = true`
- `ignore_missing_imports = true` (alguns SDKs nao expoem stubs)

## Docstrings

Estilo **Google** (renderizado pelo `mkdocstrings` na
[referencia de API](../api/index.md)):

```python
def build_provider(name: str, config: dict | None = None) -> Provider:
    """Build a provider instance by name.

    Args:
        name: Provider name (e.g. ``"anthropic"``).
        config: Optional configuration dict.

    Returns:
        A configured provider ready to be used by the agent loop.

    Raises:
        ValueError: If ``name`` is not a registered provider.

    Example:
        >>> p = build_provider("anthropic", {"api_key": "sk-ant-..."})
    """
```

Diretrizes:

- Primeira linha imperativa, com ponto final.
- Linha em branco depois da primeira linha sempre que houver `Args:`/`Returns:`.
- Use `Raises:` para excecoes documentadas como parte da API.
- `Example:` com `>>>` quando o uso nao e obvio.

## Imports

Ordem garantida pelo `ruff` (`I`):

1. **stdlib** — `asyncio`, `pathlib`, ...
2. **third-party** — `httpx`, `pydantic`, `anthropic`, ...
3. **local** — `vulpcode.*`

Sem imports relativos atravessando pacotes (`from .. import x`); use absoluto
(`from vulpcode.providers.anthropic import AnthropicProvider`).

## Comentarios

Apenas onde o **WHY** nao e obvio: invariante escondida, workaround para um
bug especifico, comportamento que surpreenderia um leitor. Codigo bem
nomeado ja descreve o **WHAT**; comentarios redundantes envelhecem mal.

## Naming

| Categoria          | Convencao              | Exemplo                |
|--------------------|------------------------|------------------------|
| Modulos            | `snake_case`           | `permissions.py`       |
| Classes            | `PascalCase`           | `AnthropicProvider`    |
| Funcoes / metodos  | `snake_case`           | `build_provider`       |
| Constantes         | `UPPER_SNAKE_CASE`     | `DEFAULT_MODEL`        |
| Privados           | prefixo `_`            | `_normalize_messages`  |
| Tools (registro)   | `PascalCase`           | `Read`, `Write`, `BashOutput` |

O nome registrado da tool (`Read`, `Bash`, ...) deve casar com o nome usado
pelos providers nas chamadas de tool — nao renomeie sem migrar os fixtures.

## Testes

- **pytest fixtures** preferidos a `setUp`/`tearDown`.
- **`pytest-asyncio`** com `asyncio_mode = "auto"` — escreva `async def
  test_*` direto, sem decorator.
- **Mocks de SDK**: `unittest.mock.patch` para o SDK oficial (anthropic,
  openai, google-genai, ollama). Use `respx` quando precisar interceptar
  `httpx` cru (provider `internal`, `WebFetch`).
- **Fixtures compartilhadas** vivem em `tests/conftest.py` e
  `tests/fixtures/`.
- **Cobertura alvo**: 70%+ no codigo critico — `providers/`, `tools/`,
  `agent.py`, `permissions.py`. Veja com:

```bash
pytest --cov=src/vulpcode --cov-report=term-missing tests/
```

## Commits

- Mensagens em portugues OK.
- Verbo no imperativo: "adiciona", "corrige", "remove", "refatora".
- Primeira linha < 72 caracteres.
- Body com contexto (motivacao, decisao, links de issue) quando a mudanca
  nao for trivial.
- Um commit por unidade logica de mudanca; evite commits gigantes que
  misturam refator + feature + fix.

Exemplo:

```
adiciona suporte a streaming no provider gemini

- traduz eventos do google-genai para o protocolo interno
- cobre cancelamento via asyncio.CancelledError
- testes em tests/test_providers/test_gemini.py

Refs #123
```

## Idioma

| Onde                                   | Idioma                |
|----------------------------------------|-----------------------|
| Codigo, identificadores, docstrings    | **Ingles**            |
| Comentarios em codigo                  | Ingles                |
| Documentacao do site (`docs/`)         | **Portugues**         |
| `mkdocs.yml`                           | Ingles (chaves) + portugues (titulos visiveis) |
| Mensagens de commit / corpo de PR      | Portugues OK          |

A justificativa: a base de codigo e consumida internacionalmente via
PyPI/GitHub; os usuarios que leem a documentacao do site sao majoritariamente
brasileiros.
