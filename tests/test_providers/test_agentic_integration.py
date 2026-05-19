"""Mock the HTTP layer of InternalLLMAgenticProvider and drive the full agent loop."""
from __future__ import annotations

import pytest
import respx
import httpx

# Make sure every tool is registered
import vulpcode.tools  # noqa: F401
import vulpcode.tools.write_py  # noqa: F401

from vulpcode.agent import Agent, ToolEndEvent, TurnEndEvent
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers.internal_llm_agentic import InternalLLMAgenticProvider
from vulpcode.tools import list_tools


ENDPOINT = "http://fake.corp/chatCompletion"


def _wrap(text: str) -> dict:
    return {"data": text}


@pytest.fixture
def provider():
    return InternalLLMAgenticProvider(
        base_url=ENDPOINT,
        user_uuid="00000000-0000-0000-0000-000000000000",
        max_retries=1,
    )


@respx.mock
@pytest.mark.asyncio
async def test_one_shot_write_py(tmp_path, provider):
    target = tmp_path / "hello.py"
    response_text = f"""\
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">{target}</vulp:arg>
  <vulp:content name="content">
print("hello")
  </vulp:content>
</vulp:tool>
"""
    ack = "Done."
    respx.post(ENDPOINT).mock(side_effect=[
        httpx.Response(200, json=_wrap(response_text)),
        httpx.Response(200, json=_wrap(ack)),
    ])
    agent = Agent(
        provider=provider,
        tools=[cls() for cls in list_tools()],
        model="internal-llm-agentic",
        permissions=PermissionManager(config={}, mode=Mode.AUTO),
    )
    events = [ev async for ev in agent.turn("create hello.py that prints hello")]
    assert any(isinstance(e, ToolEndEvent) and not e.result.is_error for e in events)
    assert target.exists()
    assert "hello" in target.read_text()


@respx.mock
@pytest.mark.asyncio
async def test_repair_loop_recovers_from_syntax_error(tmp_path, provider):
    target = tmp_path / "fib.py"
    # First response: code with a SyntaxError
    bad = f"""\
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">{target}</vulp:arg>
  <vulp:content name="content">
def fib(n):
    a, b = 0 1
    for _ in range(n):
        print(a)
        a, b = b, a + b
  </vulp:content>
</vulp:tool>
"""
    # Second response: corrected
    good = f"""\
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">{target}</vulp:arg>
  <vulp:content name="content">
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        print(a)
        a, b = b, a + b
  </vulp:content>
</vulp:tool>
"""
    # Third response: ack (no tool)
    ack = "Done."

    respx.post(ENDPOINT).mock(side_effect=[
        httpx.Response(200, json=_wrap(bad)),
        httpx.Response(200, json=_wrap(good)),
        httpx.Response(200, json=_wrap(ack)),
    ])

    agent = Agent(
        provider=provider,
        tools=[cls() for cls in list_tools()],
        model="internal-llm-agentic",
        permissions=PermissionManager(config={}, mode=Mode.AUTO),
    )
    events = [ev async for ev in agent.turn("create fibonacci script")]

    tool_ends = [e for e in events if isinstance(e, ToolEndEvent)]
    assert len(tool_ends) == 2
    assert tool_ends[0].result.is_error is True   # first attempt fails validation
    assert tool_ends[0].result.error is not None
    assert "SyntaxError" in tool_ends[0].result.error
    assert tool_ends[1].result.is_error is False  # second attempt succeeds
    assert target.exists()
    src = target.read_text()
    # Verify the GOOD version was saved (with the comma)
    assert "0, 1" in src


@respx.mock
@pytest.mark.asyncio
async def test_parse_error_surfaces_as_text(provider):
    """Malformed tool block: parser should not crash; text feedback to the model."""
    # The closing tags are intentionally absent, so the parser drops this block.
    response_text = """\
<vulp:tool name="WritePy">
  <vulp:arg name="file_path">/tmp/x.py</vulp:arg>
  <vulp:content name="content">
print("hi")
[content block and tool block never closed]
"""
    respx.post(ENDPOINT).mock(
        return_value=httpx.Response(200, json=_wrap(response_text))
    )
    agent = Agent(
        provider=provider,
        tools=[cls() for cls in list_tools()],
        model="internal-llm-agentic",
        permissions=PermissionManager(config={}, mode=Mode.AUTO),
    )
    events = [ev async for ev in agent.turn("...")]
    # No ToolEndEvent (parser dropped the malformed block)
    assert not any(isinstance(e, ToolEndEvent) for e in events)
    # But agent should still complete with a TurnEnd (text-only response)
    assert any(isinstance(e, TurnEndEvent) for e in events)
