import pytest

import vulpcode.tools  # noqa: F401
from vulpcode.tools import get_tool
from vulpcode.tools.todo import _TODO_STORE, clear_todos, get_todos  # noqa: F401


@pytest.fixture(autouse=True)
def _clean():
    clear_todos()
    yield
    clear_todos()


@pytest.mark.asyncio
async def test_todo_write_replaces_list():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    res = await cls().run(
        cls.Input(
            todos=[
                TodoItem(content="Do A", activeForm="Doing A", status="in_progress"),
            ]
        )
    )
    assert res.is_error is False
    assert len(get_todos()) == 1
    assert get_todos()[0].status == "in_progress"


@pytest.mark.asyncio
async def test_todo_at_most_one_in_progress():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    with pytest.raises(Exception):
        cls.Input(
            todos=[
                TodoItem(content="A", activeForm="a", status="in_progress"),
                TodoItem(content="B", activeForm="b", status="in_progress"),
            ]
        )


@pytest.mark.asyncio
async def test_todo_render_uses_active_form():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    res = await cls().run(
        cls.Input(
            todos=[
                TodoItem(
                    content="Implement X",
                    activeForm="Implementing X",
                    status="in_progress",
                ),
                TodoItem(content="Do Y", activeForm="Doing Y", status="pending"),
            ]
        )
    )
    assert "Implementing X" in res.output
    assert "Do Y" in res.output


@pytest.mark.asyncio
async def test_todo_completed_marker():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    res = await cls().run(
        cls.Input(
            todos=[
                TodoItem(content="A", activeForm="a", status="completed"),
            ]
        )
    )
    assert "[x]" in res.output


@pytest.mark.asyncio
async def test_todo_empty_list_ok():
    cls = get_tool("TodoWrite")
    res = await cls().run(cls.Input(todos=[]))
    assert res.is_error is False
    assert get_todos() == []


@pytest.mark.asyncio
async def test_todo_replaces_previous_list():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    await cls().run(
        cls.Input(
            todos=[
                TodoItem(content="A", activeForm="a", status="pending"),
                TodoItem(content="B", activeForm="b", status="pending"),
            ]
        )
    )
    assert len(get_todos()) == 2
    await cls().run(
        cls.Input(
            todos=[
                TodoItem(content="C", activeForm="c", status="completed"),
            ]
        )
    )
    todos = get_todos()
    assert len(todos) == 1
    assert todos[0].content == "C"


@pytest.mark.asyncio
async def test_todo_requires_no_confirm():
    cls = get_tool("TodoWrite")
    assert cls._requires_confirm is False
