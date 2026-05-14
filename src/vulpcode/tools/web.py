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


def _unavailable_message(reason: str) -> str:
    """Build a non-error, informative message when web search is unavailable."""
    return (
        f"WebSearch backend unavailable: {reason}.\n"
        "Options:\n"
        "  - set TAVILY_API_KEY env var for an alternative backend\n"
        "  - use WebFetch with a known URL instead\n"
        "  - proceed without web search using local information."
    )


def _html_to_markdown(html: str) -> str:
    """Best-effort HTML -> markdown conversion (no external dep)."""
    html = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for level in range(6, 0, -1):
        html = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, lv=level: "\n" + ("#" * lv) + " " + m.group(1).strip() + "\n",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
    html = re.sub(
        r"""<a [^>]*href=(?:"([^"]*)"|'([^']*)')[^>]*>(.*?)</a>""",
        lambda m: f"[{re.sub(r'<[^>]+>', '', m.group(3)).strip()}]({m.group(1) or m.group(2)})",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(
        r"<li[^>]*>(.*?)</li>",
        lambda m: f"- {m.group(1).strip()}\n",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(r"</p>", "\n\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<br[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", "", html)
    html = (
        html.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )
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
    """Fetch a URL and return its content as markdown.

    Performs a best-effort HTML-to-markdown conversion (no external
    dependency) and clips output to 100 000 characters. ``prompt`` is not
    interpreted locally — it is preserved so the model can use it when
    summarizing the fetched content.
    """

    class Input(BaseModel):
        url: str
        prompt: str | None = None

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, WebFetchTool.Input)
        if not args.url.startswith(("http://", "https://")):
            return ToolResult(
                error=f"URL must start with http(s)://: {args.url}",
                is_error=True,
            )
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
    """Search the web and return up to 10 results.

    Uses Tavily when ``TAVILY_API_KEY`` is set, otherwise falls back to a
    lightweight DuckDuckGo HTML scrape. ``allowed_domains`` and
    ``blocked_domains`` filter the result list client-side.
    """

    class Input(BaseModel):
        query: str
        allowed_domains: list[str] | None = None
        blocked_domains: list[str] | None = None

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, WebSearchTool.Input)
        if os.environ.get("TAVILY_API_KEY"):
            return await _search_tavily(args)
        return await _search_duckduckgo(args)


async def _search_duckduckgo(args: WebSearchTool.Input) -> ToolResult:
    """Lightweight scrape of DuckDuckGo HTML results."""
    url = "https://duckduckgo.com/html/"
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = await client.post(url, data={"q": args.query})
    except httpx.HTTPError as exc:
        return ToolResult(
            output=_unavailable_message(
                f"network error talking to DuckDuckGo ({exc})"
            ),
            metadata={"backend": "duckduckgo", "available": False},
        )

    if resp.status_code != 200:
        return ToolResult(
            output=_unavailable_message(
                f"DuckDuckGo returned HTTP {resp.status_code} "
                "(likely anti-bot redirect/block)"
            ),
            metadata={
                "backend": "duckduckgo",
                "available": False,
                "status": resp.status_code,
            },
        )

    pattern = re.compile(
        r'<a class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a class="result__snippet"[^>]*>(.*?)</a>',
        flags=re.DOTALL,
    )
    raw = resp.text
    results: list[dict[str, str]] = []
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
        return ToolResult(
            output=f"No results for {args.query!r}",
            metadata={"backend": "duckduckgo"},
        )

    body = "\n\n".join(
        f"{i + 1}. {r['title']}\n   {r['url']}\n   {r['snippet']}"
        for i, r in enumerate(results)
    )
    return ToolResult(
        output=body,
        metadata={"backend": "duckduckgo", "results": len(results)},
    )


async def _search_tavily(args: WebSearchTool.Input) -> ToolResult:
    api_key = os.environ["TAVILY_API_KEY"]
    payload: dict[str, object] = {
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
        return ToolResult(
            error=f"Tavily HTTP {resp.status_code}: {resp.text[:200]}",
            is_error=True,
        )

    data = resp.json()
    results = data.get("results", [])[:10]
    if not results:
        return ToolResult(
            output=f"No results for {args.query!r}",
            metadata={"backend": "tavily"},
        )

    body = "\n\n".join(
        f"{i + 1}. {r.get('title', '')}\n   {r.get('url', '')}\n   {r.get('content', '')}"
        for i, r in enumerate(results)
    )
    return ToolResult(
        output=body,
        metadata={"backend": "tavily", "results": len(results)},
    )
