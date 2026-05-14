import pytest

import vulpcode.tools  # noqa: F401  (registers tools)
from vulpcode.tools import get_tool
from vulpcode.tools.todo import clear_todos, get_todos


@pytest.fixture(autouse=True)
def _clean():
    clear_todos()
    yield
    clear_todos()


@pytest.mark.asyncio
async def test_todo_workflow():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    # Initial list with one in_progress
    await cls().run(
        cls.Input(
            todos=[
                TodoItem(content="A", activeForm="Doing A", status="in_progress"),
                TodoItem(content="B", activeForm="Doing B", status="pending"),
            ]
        )
    )
    # Mark A done, start B
    await cls().run(
        cls.Input(
            todos=[
                TodoItem(content="A", activeForm="Doing A", status="completed"),
                TodoItem(content="B", activeForm="Doing B", status="in_progress"),
            ]
        )
    )
    todos = get_todos()
    assert todos[0].status == "completed"
    assert todos[1].status == "in_progress"


@pytest.mark.asyncio
async def test_todo_then_read_via_helper():
    cls = get_tool("TodoWrite")
    TodoItem = cls.Input.model_fields["todos"].annotation.__args__[0]
    await cls().run(
        cls.Input(
            todos=[
                TodoItem(content="One", activeForm="Doing one", status="pending"),
                TodoItem(content="Two", activeForm="Doing two", status="pending"),
                TodoItem(content="Three", activeForm="Doing three", status="pending"),
            ]
        )
    )
    todos = get_todos()
    assert [t.content for t in todos] == ["One", "Two", "Three"]
    assert all(t.status == "pending" for t in todos)
