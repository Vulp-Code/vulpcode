"""Tests for WebFetch and WebSearch tools."""
import pytest

respx = pytest.importorskip("respx")
import httpx  # noqa: E402

import vulpcode.tools  # noqa: F401, E402
from vulpcode.tools import get_tool  # noqa: E402


@respx.mock
async def test_webfetch_html_to_markdown():
    respx.get("https://example.com/page").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><body><h1>Title</h1><p>Hello <a href='/x'>link</a></p></body></html>",
        )
    )
    cls = get_tool("WebFetch")
    res = await cls().run(cls.Input(url="https://example.com/page"))
    assert res.is_error is False
    assert "# Title" in res.output
    assert "[link](/x)" in res.output


@respx.mock
async def test_webfetch_404():
    respx.get("https://example.com/404").mock(return_value=httpx.Response(404))
    cls = get_tool("WebFetch")
    res = await cls().run(cls.Input(url="https://example.com/404"))
    assert res.is_error
    assert "404" in (res.error or "")


async def test_webfetch_invalid_scheme():
    cls = get_tool("WebFetch")
    res = await cls().run(cls.Input(url="ftp://example.com"))
    assert res.is_error


@respx.mock
async def test_webfetch_binary_content():
    respx.get("https://example.com/img.png").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=b"\x89PNG" + b"\x00" * 10,
        )
    )
    cls = get_tool("WebFetch")
    res = await cls().run(cls.Input(url="https://example.com/img.png"))
    assert res.is_error is False
    assert "binary" in res.output.lower()


@respx.mock
async def test_webfetch_truncates_large_content():
    big_text = "<p>" + ("x" * 200_000) + "</p>"
    respx.get("https://example.com/big").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=big_text,
        )
    )
    cls = get_tool("WebFetch")
    res = await cls().run(cls.Input(url="https://example.com/big"))
    assert res.is_error is False
    assert "[truncated to 100000 chars]" in res.output
    assert len(res.output) <= 100_000 + len("\n\n[truncated to 100000 chars]")


@respx.mock
async def test_webfetch_redirect_followed():
    respx.get("https://example.com/start").mock(
        return_value=httpx.Response(
            302,
            headers={"location": "https://example.com/final"},
        )
    )
    respx.get("https://example.com/final").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><body><h2>Done</h2></body></html>",
        )
    )
    cls = get_tool("WebFetch")
    res = await cls().run(cls.Input(url="https://example.com/start"))
    assert res.is_error is False
    assert "## Done" in res.output
    assert res.metadata["url"].endswith("/final")


@respx.mock
async def test_websearch_duckduckgo(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    respx.post("https://duckduckgo.com/html/").mock(
        return_value=httpx.Response(
            200,
            text=(
                '<a class="result__a" href="https://a.com/x">Title A</a>'
                '<a class="result__snippet">Snippet A</a>'
                '<a class="result__a" href="https://b.com/x">Title B</a>'
                '<a class="result__snippet">Snippet B</a>'
            ),
        )
    )
    cls = get_tool("WebSearch")
    res = await cls().run(cls.Input(query="test"))
    assert "Title A" in res.output
    assert "Snippet B" in res.output
    assert res.metadata["backend"] == "duckduckgo"


@respx.mock
async def test_websearch_blocked_domain(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    respx.post("https://duckduckgo.com/html/").mock(
        return_value=httpx.Response(
            200,
            text=(
                '<a class="result__a" href="https://blocked.com/x">B</a>'
                '<a class="result__snippet">S</a>'
                '<a class="result__a" href="https://ok.com/y">OK</a>'
                '<a class="result__snippet">SOK</a>'
            ),
        )
    )
    cls = get_tool("WebSearch")
    res = await cls().run(cls.Input(query="t", blocked_domains=["blocked.com"]))
    assert "blocked.com" not in res.output
    assert "ok.com" in res.output


@respx.mock
async def test_websearch_allowed_domain(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    respx.post("https://duckduckgo.com/html/").mock(
        return_value=httpx.Response(
            200,
            text=(
                '<a class="result__a" href="https://allowed.com/x">A</a>'
                '<a class="result__snippet">SA</a>'
                '<a class="result__a" href="https://other.com/y">O</a>'
                '<a class="result__snippet">SO</a>'
            ),
        )
    )
    cls = get_tool("WebSearch")
    res = await cls().run(cls.Input(query="t", allowed_domains=["allowed.com"]))
    assert "allowed.com" in res.output
    assert "other.com" not in res.output


@respx.mock
async def test_websearch_uses_tavily_when_key_set(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"title": "TT", "url": "https://t.com/", "content": "TC"},
                ]
            },
        )
    )
    cls = get_tool("WebSearch")
    res = await cls().run(cls.Input(query="hello"))
    assert res.is_error is False
    assert "TT" in res.output
    assert res.metadata["backend"] == "tavily"


def test_web_tools_registered():
    fetch_cls = get_tool("WebFetch")
    search_cls = get_tool("WebSearch")
    assert fetch_cls._requires_confirm is False
    assert search_cls._requires_confirm is False
