import asyncio

import pytest

import vulpcode.tools  # noqa: F401  (registers tools)
from vulpcode.tools import get_tool
from vulpcode.tools._bash_registry import _REGISTRY


@pytest.fixture(autouse=True)
def _clean():
    _REGISTRY.clear()
    yield
    _REGISTRY.clear()


@pytest.mark.asyncio
async def test_two_background_processes_parallel():
    bash = get_tool("Bash")
    bo = get_tool("BashOutput")

    res_a = await bash().run(
        bash.Input(
            command="echo a; sleep 0.2; echo done_a",
            run_in_background=True,
        )
    )
    res_b = await bash().run(
        bash.Input(
            command="echo b; sleep 0.2; echo done_b",
            run_in_background=True,
        )
    )
    a_id = res_a.metadata["bash_id"]
    b_id = res_b.metadata["bash_id"]
    assert a_id != b_id

    await asyncio.sleep(0.6)
    out_a = await bo().run(bo.Input(bash_id=a_id))
    out_b = await bo().run(bo.Input(bash_id=b_id))
    assert "a" in out_a.output and "done_a" in out_a.output
    assert "b" in out_b.output and "done_b" in out_b.output


@pytest.mark.asyncio
async def test_independent_offsets_per_process():
    bash = get_tool("Bash")
    bo = get_tool("BashOutput")

    res_a = await bash().run(
        bash.Input(
            command="echo first_a; sleep 0.1; echo second_a",
            run_in_background=True,
        )
    )
    res_b = await bash().run(
        bash.Input(command="echo only_b", run_in_background=True)
    )
    a_id = res_a.metadata["bash_id"]
    b_id = res_b.metadata["bash_id"]

    await asyncio.sleep(0.05)
    first_a = await bo().run(bo.Input(bash_id=a_id))
    await asyncio.sleep(0.4)
    second_a = await bo().run(bo.Input(bash_id=a_id))
    out_b = await bo().run(bo.Input(bash_id=b_id))

    combined_a = first_a.output + second_a.output
    assert "first_a" in combined_a
    assert "second_a" in combined_a
    assert "only_b" in out_b.output
    assert "only_b" not in combined_a
