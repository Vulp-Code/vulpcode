# Web

Duas tools para sair do localhost: pegar o conteudo de uma URL e procurar
coisas em um buscador.

| Tool        | Confirma? | Para que serve                                                          |
|-------------|-----------|-------------------------------------------------------------------------|
| `WebFetch`  | nao       | GET em uma URL, converte HTML para markdown, trunca em 100k chars.      |
| `WebSearch` | nao       | Busca DuckDuckGo (default, sem chave) ou Tavily se `TAVILY_API_KEY`.    |

Source de verdade:
[`web.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/web.py).

Dependencia em runtime: [`httpx`](https://www.python-httpx.org/) (ja
instalado pelo `pyproject.toml`).

---

## WebFetch

**Categoria:** Web  ·  **Confirma?** nao

Faz um GET HTTP na URL informada e devolve o conteudo. Se for HTML,
converte para markdown via regex (best-effort, sem libs externas tipo
BeautifulSoup); se for texto puro ou JSON, devolve cru; se for binario,
retorna so um sumario.

### Schema de input

```python
from pydantic import BaseModel


class Input(BaseModel):
    url: str
    prompt: str | None = None
```

> O campo `prompt` e **ignorado localmente** — a tool nunca consulta um
> LLM no meio do caminho. Ele e um lembrete que o **modelo principal**
> grava para si mesmo, dizendo "quando eu ler o output, o que eu queria
> extrair era X". Aparece em `metadata["prompt"]` mas nao muda a
> requisicao.

### Comportamento

- Aceita so `http://` ou `https://`. Outros esquemas (`file://`, `ftp://`)
  retornam erro `URL must start with http(s)://`.
- Cliente: `httpx.AsyncClient`, `follow_redirects=True`,
  `timeout=30s`, header `User-Agent: Mozilla/5.0 (vulpcode/0.1)`.
- HTTP `>= 400` vira erro com `is_error=True` e
  `metadata = {"url": ..., "status": ..., "content_type": ..., "prompt": ...}`.
- Conversao por `Content-Type`:

    | Content-Type contem...                | O que sai                                                                  |
    |---------------------------------------|----------------------------------------------------------------------------|
    | `text/html` ou `application/xhtml`    | HTML convertido para markdown (`<h1..6>`, `<a>`, `<li>`, `<p>`, `<br>` e tags removidas; entidades comuns decodificadas). |
    | `text/*` ou `application/json`        | `resp.text` cru.                                                           |
    | qualquer outra coisa                  | `<binary content: <ctype>, <N> bytes>` — **nao baixa o binario**, so reporta. |

- **Truncamento**: se o texto convertido passa de **100 000 chars**, e
  cortado e adicionado `\n\n[truncated to 100000 chars]`.
- A conversao HTML→markdown e regex pura — funciona razoavelmente em
  paginas simples, mas nao executa JavaScript. Single-page apps que
  renderizam o conteudo no browser **vao retornar markup vazio**.

### Exemplo (no REPL)

```text
> baixe https://docs.python.org/3/library/asyncio.html e me diga
  o que mudou na 3.12
```

(O modelo chama `WebFetch({"url": "...", "prompt": "..."})`, le o
markdown convertido e responde.)

### Exemplo (programatico)

```python
from vulpcode.tools import get_tool

WebFetchTool = get_tool("WebFetch")

result = await WebFetchTool().run(
    WebFetchTool.Input(
        url="https://example.com",
        prompt="qual e o titulo da pagina?",
    )
)
print(result.output[:200])
print(result.metadata)
# {"url": "https://example.com", "status": 200,
#  "content_type": "text/html; charset=UTF-8", "prompt": "..."}
```

### Limitacoes

- Sem JavaScript: SPAs entregam HTML vazio.
- Sem cookies/auth/headers extras alem do `User-Agent`. Para paginas
  atras de login, baixe localmente e use `Read`.
- Conteudo binario nao e baixado — voce ve so um placeholder. Para
  binarios use [`Bash`](search-and-shell.md#bash) com `curl`/`wget`.
- Conversao regex erra em HTML mal-formado e em estruturas aninhadas
  pesadas (tabelas complexas, `<pre>` com tags por dentro).

### Fonte

`src/vulpcode/tools/web.py`

---

## WebSearch

**Categoria:** Web  ·  **Confirma?** nao

Busca textual na web. **Por padrao**, faz scraping leve da pagina HTML do
DuckDuckGo (sem chave, sem cadastro). Se a variavel de ambiente
`TAVILY_API_KEY` estiver setada no momento da chamada, troca para a API
do **Tavily**.

### Schema de input

```python
from pydantic import BaseModel


class Input(BaseModel):
    query: str
    allowed_domains: list[str] | None = None    # filtro inclusivo (host contem)
    blocked_domains: list[str] | None = None    # filtro exclusivo (host contem)
```

Limite duro de **10 resultados** em ambos os backends. Os filtros sao
aplicados sobre o `hostname` parseado da URL — match por substring (`"github.com"`
casa `api.github.com`, `gist.github.com`, etc).

### Selecao de backend

A escolha acontece em cada chamada, dentro de `WebSearchTool.run`:

```python
if os.environ.get("TAVILY_API_KEY"):
    return await _search_tavily(args)
return await _search_duckduckgo(args)
```

Setou `TAVILY_API_KEY` depois de abrir o REPL? Pode ser preciso reiniciar
para garantir — em geral o env e lido a cada chamada, mas se voce
exportou em outro shell, esse processo do REPL nao enxerga.

### Notas importantes sobre o DuckDuckGo (DDG)

A partir de **2024**, o DuckDuckGo apertou as defesas anti-bot. O endpoint
`https://duckduckgo.com/html/` que a tool usa frequentemente retorna **HTTP
302 / 403** (redirect para CAPTCHA, ou bloqueio direto) quando detecta
trafego automatizado. Quando isso acontece:

- O vulpcode **NAO** trata como erro (nao retorna `is_error=True`). Em
  vez disso, devolve uma mensagem informativa explicando o que houve e
  sugerindo proximos passos:

    ```text
    WebSearch backend unavailable: DuckDuckGo returned HTTP 302
    (likely anti-bot redirect/block).
    Options:
      - set TAVILY_API_KEY env var for an alternative backend
      - use WebFetch with a known URL instead
      - proceed without web search using local information.
    ```

- A `metadata` traz `{"backend": "duckduckgo", "available": False, "status": <codigo>}`.
- Por que **nao** e `is_error=True`? Porque um erro fariam o LLM tentar
  re-executar a busca em loop. A mensagem informativa orienta o modelo a
  trocar de estrategia (Tavily, WebFetch direto, ou seguir sem busca) em
  vez de bater na mesma porta.
- Erros de rede (DNS, timeout) entram no mesmo caminho, com mensagem
  `network error talking to DuckDuckGo (...)`.

Em outras palavras: **se a primeira `WebSearch` retornar a mensagem de
"backend unavailable", isso e esperado, nao bug.** Configure Tavily se
voce vai depender de busca.

### Tavily — fallback recomendado

[Tavily](https://tavily.com) e um motor de busca focado em LLMs. Plano
gratuito permite **1 000 buscas/mes** — suficiente para uso pessoal e
desenvolvimento.

Setup:

1. Crie uma conta em [https://tavily.com](https://tavily.com).
2. Pegue a API key no dashboard (formato `tvly-...`).
3. Exporte a variavel:

    ```bash
    export TAVILY_API_KEY=tvly-...
    ```

4. Reinicie o REPL — `WebSearch` agora usa Tavily automaticamente.

A integracao chama `POST https://api.tavily.com/search` com payload:

```json
{
  "api_key": "tvly-...",
  "query": "<query>",
  "max_results": 10,
  "search_depth": "basic",
  "include_domains": ["..."],
  "exclude_domains": ["..."]
}
```

`include_domains` e `exclude_domains` so vao se voce passou
`allowed_domains` / `blocked_domains` na chamada da tool.

Diferente do DDG, o backend Tavily **trata HTTP != 200 como erro**
(`Tavily HTTP 401: ...`). Plano expirado, key invalida, ou rate-limit
viram `is_error=True`.

### Output

Em ambos os backends, o `output` e uma lista numerada:

```text
1. Titulo do primeiro resultado
   https://exemplo.com/path
   Snippet curto descrevendo a pagina.

2. Segundo resultado
   https://outro.com/path
   Snippet do segundo.
```

`metadata`:

- DuckDuckGo OK: `{"backend": "duckduckgo", "results": <N>}`.
- DuckDuckGo bloqueado: `{"backend": "duckduckgo", "available": False, "status": <codigo>}`.
- Tavily OK: `{"backend": "tavily", "results": <N>}`.

Sem resultados em qualquer backend: `output="No results for '<query>'"`,
`metadata={"backend": ...}`. **Nao e erro.**

### Exemplo (no REPL)

```text
> busque "python 3.13 release notes"
```

Com filtro de dominio:

```text
> busque "asyncio gather vs taskgroup" so em docs.python.org
```

### Exemplo (programatico)

```python
import os
from vulpcode.tools import get_tool

WebSearchTool = get_tool("WebSearch")

# Default: DuckDuckGo. Talvez retorne mensagem de "unavailable".
result = await WebSearchTool().run(
    WebSearchTool.Input(query="python 3.13 release notes")
)
print(result.metadata.get("backend"))  # "duckduckgo"
print(result.output)

# Tavily: setar antes da chamada.
os.environ["TAVILY_API_KEY"] = "tvly-..."

result = await WebSearchTool().run(
    WebSearchTool.Input(
        query="asyncio gather vs taskgroup",
        allowed_domains=["docs.python.org"],
    )
)
print(result.metadata)  # {"backend": "tavily", "results": ...}
```

### Limitacoes

- DDG so funciona enquanto o anti-bot deles deixar — pode quebrar a
  qualquer momento sem aviso.
- Filtros sao por substring no hostname — `"google.com"` casa
  `mail.google.com` mas tambem `googleblog.com` (substring no host
  parseado, nao match exato).
- Sem paginacao alem dos 10 primeiros resultados.
- Sem timestamp/freshness controlavel (Tavily tem, mas a tool nao expoe
  ainda).

### Fonte

`src/vulpcode/tools/web.py`

---

## Veja tambem

- [Filesystem](filesystem.md) — `Read`, `Write`, `Edit`, `MultiEdit`,
  `Glob`.
- [Busca e Shell](search-and-shell.md) — `Grep`, `Bash`, `BashOutput`,
  `KillBash`. Para conteudos binarios ou paginas atras de login, use
  `Bash` com `curl`/`wget`.
- [Agente](agent.md) — `Task` lanca sub-agentes que herdam `WebFetch` /
  `WebSearch` no perfil `general-purpose`.
