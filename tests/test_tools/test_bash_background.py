import asyncio

import pytest

import vulpcode.tools  # noqa: F401  (registers tools)
from vulpcode.tools import get_tool
from vulpcode.tools._bash_registry import _REGISTRY


@pytest.fixture(autouse=True)
def _clean_registry():
    _REGISTRY.clear()
    yield
    _REGISTRY.clear()


@pytest.mark.asyncio
async def test_bashoutput_returns_incremental():
    bash = get_tool("Bash")
    bo = get_tool("BashOutput")
    res = await bash().run(
        bash.Input(
            command="echo line1; sleep 0.1; echo line2",
            run_in_background=True,
        )
    )
    bash_id = res.metadata["bash_id"]
    await asyncio.sleep(0.05)
    first = await bo().run(bo.Input(bash_id=bash_id))
    await asyncio.sleep(0.3)
    second = await bo().run(bo.Input(bash_id=bash_id))
    assert "line2" in (first.output + second.output)
    assert "completed" in second.output or "running" in first.output


@pytest.mark.asyncio
async def test_bashoutput_filter():
    bash = get_tool("Bash")
    bo = get_tool("BashOutput")
    res = await bash().run(
        bash.Input(
            command="echo INFO ok; echo DEBUG noise",
            run_in_background=True,
        )
    )
    bash_id = res.metadata["bash_id"]
    await asyncio.sleep(0.4)
    out = await bo().run(bo.Input(bash_id=bash_id, filter=r"^INFO"))
    assert "INFO" in out.output
    assert "DEBUG" not in out.output


@pytest.mark.asyncio
async def test_bashoutput_unknown_id():
    bo = get_tool("BashOutput")
    res = await bo().run(bo.Input(bash_id="nope"))
    assert res.is_error


@pytest.mark.asyncio
async def test_bashoutput_invalid_regex():
    bash = get_tool("Bash")
    bo = get_tool("BashOutput")
    res = await bash().run(
        bash.Input(command="echo hi", run_in_background=True)
    )
    bash_id = res.metadata["bash_id"]
    await asyncio.sleep(0.2)
    out = await bo().run(bo.Input(bash_id=bash_id, filter="[unclosed"))
    assert out.is_error
    assert "regex" in (out.error or "").lower()


@pytest.mark.asyncio
async def test_bashoutput_status_completed():
    bash = get_tool("Bash")
    bo = get_tool("BashOutput")
    res = await bash().run(
        bash.Input(command="echo done", run_in_background=True)
    )
    bash_id = res.metadata["bash_id"]
    await asyncio.sleep(0.4)
    out = await bo().run(bo.Input(bash_id=bash_id))
    assert "completed" in out.output
    assert out.metadata["running"] is False


@pytest.mark.asyncio
async def test_killbash_terminates():
    bash = get_tool("Bash")
    kill = get_tool("KillBash")
    res = await bash().run(
        bash.Input(command="sleep 30", run_in_background=True)
    )
    bash_id = res.metadata["bash_id"]
    await asyncio.sleep(0.05)
    kres = await kill().run(kill.Input(bash_id=bash_id))
    assert kres.is_error is False
    assert "Killed" in kres.output
    assert bash_id not in _REGISTRY


@pytest.mark.asyncio
async def test_killbash_already_done():
    bash = get_tool("Bash")
    kill = get_tool("KillBash")
    res = await bash().run(
        bash.Input(command="echo bye", run_in_background=True)
    )
    bash_id = res.metadata["bash_id"]
    await asyncio.sleep(0.4)
    kres = await kill().run(kill.Input(bash_id=bash_id))
    assert kres.is_error is False
    assert kres.metadata.get("already_done") is True


@pytest.mark.asyncio
async def test_killbash_unknown_id():
    kill = get_tool("KillBash")
    res = await kill().run(kill.Input(bash_id="nope"))
    assert res.is_error


def test_killbash_requires_confirm():
    cls = get_tool("KillBash")
    assert cls._requires_confirm is True


def test_bashoutput_does_not_require_confirm():
    cls = get_tool("BashOutput")
    assert cls._requires_confirm is False
