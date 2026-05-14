"""Tests for Tool ABC, @tool decorator, registry, and execute_tool_call."""
import pytest
from pydantic import BaseModel

from vulpcode.providers import ToolCall
from vulpcode.tools import (
    Tool,
    ToolResult,
    clear_registry,
    execute_tool_call,
    get_tool,
    list_tools,
    tool,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_decorator_registers_tool():
    @tool(name="Echo", description="echoes back")
    class EchoTool(Tool):
        class Input(BaseModel):
            text: str

        async def run(self, args):
            return ToolResult(output=args.text)

    assert get_tool("Echo") is EchoTool
    assert EchoTool._tool_name == "Echo"
    assert EchoTool._requires_confirm is False
    assert list_tools() == [EchoTool]


def test_decorator_requires_input_class():
    with pytest.raises(TypeError):

        @tool(name="NoInput", description="bad")
        class NoInput(Tool):
            async def run(self, args):
                return ToolResult()


def test_decorator_rejects_non_tool():
    with pytest.raises(TypeError):

        @tool(name="X", description="x")
        class NotATool:  # type: ignore[misc]
            class Input(BaseModel):
                x: int


def test_duplicate_name_rejected():
    @tool(name="Dup", description="d")
    class A(Tool):
        class Input(BaseModel):
            pass

        async def run(self, args):
            return ToolResult()

    with pytest.raises(ValueError):

        @tool(name="Dup", description="d2")
        class B(Tool):
            class Input(BaseModel):
                pass

            async def run(self, args):
                return ToolResult()


def test_to_schema():
    @tool(name="Add", description="adds")
    class AddTool(Tool):
        class Input(BaseModel):
            a: int
            b: int

        async def run(self, args):
            return ToolResult(output=str(args.a + args.b))

    schema = AddTool.to_schema()
    assert schema["name"] == "Add"
    assert schema["description"] == "adds"
    assert schema["input_schema"]["properties"]["a"]["type"] == "integer"
    assert schema["input_schema"]["properties"]["b"]["type"] == "integer"


def test_requires_confirm_flag():
    @tool(name="Risky", description="dangerous", requires_confirm=True)
    class Risky(Tool):
        class Input(BaseModel):
            pass

        async def run(self, args):
            return ToolResult()

    assert Risky._requires_confirm is True


def test_get_tool_unknown_raises():
    with pytest.raises(KeyError):
        get_tool("DoesNotExist")


def test_tool_result_to_string():
    ok = ToolResult(output="hello")
    assert ok.to_string() == "hello"
    err = ToolResult(error="boom", is_error=True)
    assert err.to_string() == "Error: boom"
    err2 = ToolResult(output="fallback", is_error=True)
    assert err2.to_string() == "Error: fallback"


@pytest.mark.asyncio
async def test_execute_tool_call_happy_path():
    @tool(name="Hello", description="h")
    class Hello(Tool):
        class Input(BaseModel):
            who: str

        async def run(self, args):
            return ToolResult(output=f"hi {args.who}")

    tc = ToolCall(id="1", name="Hello", arguments={"who": "world"})
    res = await execute_tool_call(tc)
    assert res.output == "hi world"
    assert not res.is_error


@pytest.mark.asyncio
async def test_execute_tool_call_invalid_args():
    @tool(name="Need", description="n")
    class Need(Tool):
        class Input(BaseModel):
            x: int

        async def run(self, args):
            return ToolResult(output=str(args.x))

    tc = ToolCall(id="1", name="Need", arguments={})
    res = await execute_tool_call(tc)
    assert res.is_error
    assert "Invalid arguments" in (res.error or "")


@pytest.mark.asyncio
async def test_execute_tool_call_unknown():
    tc = ToolCall(id="1", name="Nope", arguments={})
    with pytest.raises(KeyError):
        await execute_tool_call(tc)
    res = await execute_tool_call(tc, allow_unknown=True)
    assert res.is_error


@pytest.mark.asyncio
async def test_execute_tool_call_run_exception():
    @tool(name="Boom", description="b")
    class Boom(Tool):
        class Input(BaseModel):
            pass

        async def run(self, args):
            raise RuntimeError("kaboom")

    tc = ToolCall(id="1", name="Boom", arguments={})
    res = await execute_tool_call(tc)
    assert res.is_error
    assert "RuntimeError" in (res.error or "")
    assert "kaboom" in (res.error or "")
