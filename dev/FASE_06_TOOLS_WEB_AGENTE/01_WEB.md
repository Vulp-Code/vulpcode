# Tarefa 06.01 - Tools WebFetch e WebSearch

**Status**: PENDENTE
**Fase**: 06 - Tools Web + Agente
**Dependencias**: 02.02
**Bloqueia**: Nada

---

## Objetivo

Implementar `WebFetch` e `WebSearch` em `src/vulpcode/tools/web.py`. WebFetch
baixa uma URL e converte HTML em markdown. WebSearch retorna resultados de busca
(default: DuckDuckGo via scraping; opcional: Tavily via env var).

---

## Descricao Tecnica

### WebFetch

**Comportamento**:
- `url`: URL absoluta (http/https).
- `prompt`: instrucao opcional sobre o que extrair (apenas anotada na metadata —
  nao processada localmente; o LLM usa).
- Baixa via httpx, segue redirects, timeout 30s.
- Converte HTML -> markdown limitando o conteudo a 100k chars.
- Retorna texto markdown como `output`.
- Se URL e binaria (imagem, PDF, etc), retorna metadata sem converter.

**Schema**:
```python
class Input(BaseModel):
    url: str
    prompt: str | None = None
```

### WebSearch

**Comportamento**:
- `query`: texto da busca.
- Backend default: DuckDuckGo HTML scrape (sem API key necessaria).
- Backend opcional: Tavily se `TAVILY_API_KEY` estiver definido.
- Retorna lista numerada de `{title, url, snippet}`.
- Limita a 10 resultados.
- `allowed_domains` / `blocked_domains` filtram resultados.

**Schema**:
```python
class Input(BaseModel):
    query: str
    allowed_domains: list[str] | None = None
    blocked_domains: list[str] | None = None
```

### Estrutura

**`src/vulpcode/tools/web.py`**:

```python
"""WebFetch and WebSearch tools."""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from vulpcode.tools.base import Tool, ToolResult, tool


_FETCH_TIMEOUT = 30.0
_FETCH_MAX_CHARS = 100_000
_USER_AGENT = "Mozilla/5.0 (vulpcode/0.1)"


def _html_to_markdown(html: str) -> str:
    """Best-effort HTML -> markdown conversion (no external dep)."""
    # Strip script/style blocks
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Headings
    for level in range(6, 0, -1):
        html = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, lv=level: "\n" + ("#" * lv) + " " + m.group(1).strip() + "\n",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
    # Anchors -> [text](href)
    html = re.sub(
        r'<a [^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        lambda m: f"[{re.sub(r'<[^>]+>', '', m.group(2)).strip()}]({m.group(1)})",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Lists
    html = re.sub(r"<li[^>]*>(.*?)</li>", lambda m: f"- {m.group(1).strip()}\n", html, flags=re.DOTALL | re.IGNORECASE)
    # Paragraphs and breaks
    html = re.sub(r"</p>", "\n\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<br[^>]*>", "\n", html, flags=re.IGNORECASE)
    # Strip remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # HTML entities (minimal)
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    # Collapse whitespace
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


@tool(
    name="WebFetch",
    description=(
        "Fetch a URL and return the page content as markdown. The optional `prompt` "
        "field is ignored locally — the LLM is expected to use it when interpreting "
        "the returned content."
    ),
    requires_confirm=False,
)
class WebFetchTool(Tool):
    class Input(BaseModel):
        url: str
        prompt: str | None = None

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, WebFetchTool.Input)
        if not args.url.startswith(("http://", "https://")):
            return ToolResult(error=f"URL must start with http(s)://: {args.url}", is_error=True)
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=_FETCH_TIMEOUT,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                resp = await client.get(args.url)
        except httpx.HTTPError as exc:
            return ToolResult(error=f"Fetch failed: {exc}", is_error=True)

        ctype = resp.headers.get("content-type", "").lower()
        meta = {
            "url": str(resp.url),
            "status": resp.status_code,
            "content_type": ctype,
            "prompt": args.prompt,
        }
        if resp.status_code >= 400:
            return ToolResult(
                error=f"HTTP {resp.status_code} fetching {args.url}",
                is_error=True,
                metadata=meta,
            )

        if "text/html" in ctype or "application/xhtml" in ctype:
            text = _html_to_markdown(resp.text)
        elif "text/" in ctype or "application/json" in ctype:
            text = resp.text
        else:
            return ToolResult(
                output=f"<binary content: {ctype}, {len(resp.content)} bytes>",
                metadata=meta,
            )
        if len(text) > _FETCH_MAX_CHARS:
            text = text[:_FETCH_MAX_CHARS] + f"\n\n[truncated to {_FETCH_MAX_CHARS} chars]"
        return ToolResult(output=text, metadata=meta)


@tool(
    name="WebSearch",
    description=(
        "Search the web. Default backend is DuckDuckGo (no key); set TAVILY_API_KEY "
        "to use Tavily. Returns up to 10 results."
    ),
    requires_confirm=False,
)
class WebSearchTool(Tool):
    class Input(BaseModel):
        query: str
        allowed_domains: list[str] | None = None
        blocked_domains: list[str] | None = None

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, WebSearchTool.Input)
        if os.environ.get("TAVILY_API_KEY"):
            return await _search_tavily(args)
        return await _search_duckduckgo(args)


async def _search_duckduckgo(args: "WebSearchTool.Input") -> ToolResult:
    """Lightweight scrape of DuckDuckGo HTML results."""
    url = "https://duckduckgo.com/html/"
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = await client.post(url, data={"q": args.query})
    except httpx.HTTPError as exc:
        return ToolResult(error=f"WebSearch failed: {exc}", is_error=True)

    if resp.status_code != 200:
        return ToolResult(error=f"DuckDuckGo HTTP {resp.status_code}", is_error=True)

    # Very simple result extraction
    pattern = re.compile(
        r'<a class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a class="result__snippet"[^>]*>(.*?)</a>',
        flags=re.DOTALL,
    )
    raw = resp.text
    results = []
    for m in pattern.finditer(raw):
        u, title_html, snippet_html = m.group(1), m.group(2), m.group(3)
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_html).strip()
        host = urlparse(u).hostname or ""
        if args.allowed_domains and not any(d in host for d in args.allowed_domains):
            continue
        if args.blocked_domains and any(d in host for d in args.blocked_domains):
            continue
        results.append({"title": title, "url": u, "snippet": snippet})
        if len(results) >= 10:
            break

    if not results:
        return ToolResult(output=f"No results for {args.query!r}", metadata={"backend": "duckduckgo"})

    body = "\n\n".join(
        f"{i + 1}. {r['title']}\n   {r['url']}\n   {r['snippet']}"
        for i, r in enumerate(results)
    )
    return ToolResult(output=body, metadata={"backend": "duckduckgo", "results": len(results)})


async def _search_tavily(args: "WebSearchTool.Input") -> ToolResult:
    api_key = os.environ["TAVILY_API_KEY"]
    payload = {
        "api_key": api_key,
        "query": args.query,
        "max_results": 10,
        "search_depth": "basic",
    }
    if args.allowed_domains:
        payload["include_domains"] = args.allowed_domains
    if args.blocked_domains:
        payload["exclude_domains"] = args.blocked_domains
    try:
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
            resp = await client.post("https://api.tavily.com/search", json=payload)
    except httpx.HTTPError as exc:
        return ToolResult(error=f"Tavily request failed: {exc}", is_error=True)

    if resp.status_code != 200:
        return ToolResult(error=f"Tavily HTTP {resp.status_code}: {resp.text[:200]}", is_error=True)

    data = resp.json()
    results = data.get("results", [])[:10]
    if not results:
        return ToolResult(output=f"No results for {args.query!r}", metadata={"backend": "tavily"})

    body = "\n\n".join(
        f"{i + 1}. {r.get('title', '')}\n   {r.get('url', '')}\n   {r.get('content', '')}"
        for i, r in enumerate(results)
    )
    return ToolResult(output=body, metadata={"backend": "tavily", "results": len(results)})
```

### Atualizar `tools/__init__.py`

```python
from vulpcode.tools import web as _web  # noqa: F401
```

---

## INSTRUCAO CRITICA

- Conversao HTML->markdown e best-effort com regex. Nao usamos lib externa
  (`html2text`, `markdownify`) para evitar dependencia. Para sites complexos o
  resultado e razoavel; para SPAs/JS-heavy nao funciona — comportamento aceito.
- Default backend de WebSearch e DuckDuckGo HTML scrape (gratuito). Tavily se
  `TAVILY_API_KEY` definido. Brave/Google poderiam ser adicionados em fase
  futura.
- DuckDuckGo pode bloquear scraping repetido. Aceitar e documentar limitacao.
- Truncar conteudo a 100k chars para nao explodir o contexto do LLM.
- Filtros `allowed_domains` / `blocked_domains` aplicados na URL host.
- `prompt` em WebFetch nao e processado localmente — apenas anotado na metadata
  para o LLM ter referencia.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/web.py`

### Etapa 2: Atualizar `tools/__init__.py`

### Etapa 3: Criar `tests/test_tools/test_web.py`

```python
import pytest
import respx
import httpx

import vulpcode.tools  # noqa
from vulpcode.tools import get_tool


@pytest.mark.asyncio
@respx.mock
async def test_webfetch_html_to_markdown():
    respx.get("https://example.com/page").mock(return_value=httpx.Response(
        200,
        headers={"content-type": "text/html"},
        text="<html><body><h1>Title</h1><p>Hello <a href='/x'>link</a></p></body></html>",
    ))
    cls = get_tool("WebFetch")
    res = await cls().run(cls.Input(url="https://example.com/page"))
    assert res.is_error is False
    assert "# Title" in res.output
    assert "[link](/x)" in res.output


@pytest.mark.asyncio
@respx.mock
async def test_webfetch_404():
    respx.get("https://example.com/404").mock(return_value=httpx.Response(404))
    cls = get_tool("WebFetch")
    res = await cls().run(cls.Input(url="https://example.com/404"))
    assert res.is_error
    assert "404" in (res.error or "")


@pytest.mark.asyncio
async def test_webfetch_invalid_scheme():
    cls = get_tool("WebFetch")
    res = await cls().run(cls.Input(url="ftp://example.com"))
    assert res.is_error


@pytest.mark.asyncio
@respx.mock
async def test_webfetch_binary_content():
    respx.get("https://example.com/img.png").mock(return_value=httpx.Response(
        200,
        headers={"content-type": "image/png"},
        content=b"\x89PNG" + b"\x00" * 10,
    ))
    cls = get_tool("WebFetch")
    res = await cls().run(cls.Input(url="https://example.com/img.png"))
    assert res.is_error is False
    assert "binary" in res.output.lower()


@pytest.mark.asyncio
@respx.mock
async def test_websearch_duckduckgo(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    respx.post("https://duckduckgo.com/html/").mock(return_value=httpx.Response(
        200,
        text=(
            '<a class="result__a" href="https://a.com/x">Title A</a>'
            '<a class="result__snippet">Snippet A</a>'
            '<a class="result__a" href="https://b.com/x">Title B</a>'
            '<a class="result__snippet">Snippet B</a>'
        ),
    ))
    cls = get_tool("WebSearch")
    res = await cls().run(cls.Input(query="test"))
    assert "Title A" in res.output
    assert "Snippet B" in res.output


@pytest.mark.asyncio
@respx.mock
async def test_websearch_blocked_domain(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    respx.post("https://duckduckgo.com/html/").mock(return_value=httpx.Response(
        200,
        text=(
            '<a class="result__a" href="https://blocked.com/x">B</a>'
            '<a class="result__snippet">S</a>'
        ),
    ))
    cls = get_tool("WebSearch")
    res = await cls().run(cls.Input(query="t", blocked_domains=["blocked.com"]))
    assert "blocked.com" not in res.output
```

**Observacao**: estes testes requerem `respx`. Se nao instalado, marcar com
`pytest.importorskip("respx")` no topo.

### Etapa 4: Adicionar `respx` em dev deps (opcional)

Em `pyproject.toml` `[project.optional-dependencies].dev` adicionar `respx>=0.21`.

### Etapa 5: Rodar testes

```bash
pip install respx
pytest tests/test_tools/test_web.py -v
```

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/web.py` implementa `WebFetchTool` e `WebSearchTool`
- [x] WebFetch valida scheme http(s), segue redirects, converte HTML->markdown
- [x] WebFetch trunca conteudo a 100k chars
- [x] WebFetch trata content-types binarios sem converter
- [x] WebSearch usa DuckDuckGo por default, Tavily se `TAVILY_API_KEY` existir
- [x] WebSearch aplica `allowed_domains` / `blocked_domains`
- [x] Ambas com `requires_confirm=False`
- [x] `tools/__init__.py` importa `web.py`
- [x] `respx>=0.21` adicionado em dev deps
- [x] `tests/test_tools/test_web.py` com >=5 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| HTML conversao perde estrutura | Alta | Medio | Aceitar v1; fase futura pode usar BeautifulSoup |
| DuckDuckGo bloqueia scraping | Media | Alto | Documentar uso de Tavily como alternativa |
| Sites JS-heavy retornam pouca info | Alta | Baixo | Aceitar v1 |
| Rate limiting | Media | Medio | Sem retry — falha rapida |

---

**End of Specification**
