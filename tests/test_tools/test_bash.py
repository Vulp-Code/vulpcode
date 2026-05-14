import asyncio

import pytest

import vulpcode.tools  # noqa: F401  (ensures all tools are registered)
from vulpcode.tools import get_tool
from vulpcode.tools._bash_registry import _REGISTRY, list_all


@pytest.fixture(autouse=True)
def _clean_registry():
    _REGISTRY.clear()
    yield
    _REGISTRY.clear()


@pytest.mark.asyncio
async def test_bash_simple_echo():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="echo hello"))
    assert res.is_error is False
    assert "hello" in res.output


@pytest.mark.asyncio
async def test_bash_nonzero_exit():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="exit 7"))
    assert res.is_error
    assert res.metadata["exit_code"] == 7


@pytest.mark.asyncio
async def test_bash_pipe():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="printf 'a\\nb\\nc\\n' | head -n 2"))
    assert "a" in res.output and "b" in res.output and "c" not in res.output


@pytest.mark.asyncio
async def test_bash_timeout():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="sleep 5", timeout=200))
    assert res.is_error
    assert "timed out" in (res.error or "")


@pytest.mark.asyncio
async def test_bash_background_registers():
    cls = get_tool("Bash")
    res = await cls().run(
        cls.Input(command="sleep 0.1; echo done", run_in_background=True)
    )
    assert res.is_error is False
    bash_id = res.metadata["bash_id"]
    assert bash_id in {bp.bash_id for bp in list_all()}
    # Wait for completion
    await asyncio.sleep(0.5)


@pytest.mark.asyncio
async def test_bash_stderr_captured():
    cls = get_tool("Bash")
    res = await cls().run(cls.Input(command="echo OUT; echo ERR 1>&2"))
    assert "OUT" in res.output and "ERR" in res.output


@pytest.mark.asyncio
async def test_bash_output_truncation():
    cls = get_tool("Bash")
    # Generate output exceeding 30k chars
    res = await cls().run(
        cls.Input(command="head -c 40000 /dev/zero | tr '\\0' 'x'")
    )
    assert res.is_error is False
    assert "[truncated, full output" in res.output
    assert len(res.output) < 40000 + 200


def test_bash_requires_confirm():
    cls = get_tool("Bash")
    assert cls._requires_confirm is True
