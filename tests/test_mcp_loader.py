import pytest

from vulpcode.mcp.loader import _resolve_env, start_configured_servers


def test_resolve_env_basic(monkeypatch):
    monkeypatch.setenv("FOO", "bar")
    out = _resolve_env({"X": "${FOO}", "Y": "literal"})
    assert out["X"] == "bar"
    assert out["Y"] == "literal"


def test_resolve_env_missing(monkeypatch):
    monkeypatch.delenv("MISSING", raising=False)
    out = _resolve_env({"X": "${MISSING}"})
    assert out["X"] == ""


def test_resolve_env_non_string_values():
    out = _resolve_env({"NUM": 42, "BOOL": True})
    assert out["NUM"] == "42"
    assert out["BOOL"] == "True"


def test_resolve_env_empty():
    assert _resolve_env({}) == {}


@pytest.mark.asyncio
async def test_start_configured_servers_empty_config():
    servers = await start_configured_servers({})
    assert servers == []


@pytest.mark.asyncio
async def test_start_configured_servers_no_servers_key():
    servers = await start_configured_servers({"mcp": {}})
    assert servers == []


@pytest.mark.asyncio
async def test_start_configured_servers_skips_invalid_entries():
    cfg = {
        "mcp": {
            "servers": [
                {"name": "", "command": "x"},
                {"name": "no-cmd"},
                {"command": "no-name"},
            ]
        }
    }
    servers = await start_configured_servers(cfg)
    assert servers == []


@pytest.mark.asyncio
async def test_start_configured_servers_isolates_failures(monkeypatch, capsys):
    """A failing server must not block the others from being started."""
    from vulpcode.mcp import loader as loader_mod

    calls: list[str] = []

    class FakeServer:
        def __init__(self, name: str) -> None:
            self.name = name
            self.tool_classes: list = []

    async def fake_connect(name, command, args=None, env=None):
        calls.append(name)
        if name == "broken":
            raise RuntimeError("boom")
        return FakeServer(name)

    monkeypatch.setattr(loader_mod, "connect_mcp_server", fake_connect)

    cfg = {
        "mcp": {
            "servers": [
                {"name": "ok1", "command": "node"},
                {"name": "broken", "command": "node"},
                {"name": "ok2", "command": "node"},
            ]
        }
    }
    servers = await start_configured_servers(cfg)
    assert [s.name for s in servers] == ["ok1", "ok2"]
    assert calls == ["ok1", "broken", "ok2"]
    captured = capsys.readouterr()
    assert "broken" in captured.out


@pytest.mark.asyncio
async def test_stop_servers_swallows_exceptions():
    from vulpcode.mcp.loader import stop_servers

    class ServerOk:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    class ServerBad:
        async def aclose(self) -> None:
            raise RuntimeError("nope")

    ok = ServerOk()
    bad = ServerBad()
    await stop_servers([ok, bad])  # must not raise
    assert ok.closed is True
