"""TodoWrite tool: in-memory todo list managed by the LLM."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from vulpcode.tools.base import Tool, ToolResult, tool


_TODO_STORE: dict[str, list["TodoItem"]] = {}
_DEFAULT_SESSION = "default"


class TodoItem(BaseModel):
    content: str
    activeForm: str
    status: Literal["pending", "in_progress", "completed"]


def get_todos(session_id: str = _DEFAULT_SESSION) -> list[TodoItem]:
    return list(_TODO_STORE.get(session_id, []))


def clear_todos(session_id: str = _DEFAULT_SESSION) -> None:
    _TODO_STORE.pop(session_id, None)


@tool(
    name="TodoWrite",
    description=(
        "Replace the agent's todo list. Each item has content (imperative), "
        "activeForm (progressive), and status. Only one item may be 'in_progress'."
    ),
    requires_confirm=False,
)
class TodoWriteTool(Tool):
    """Replace the agent's in-memory todo list.

    Each item carries ``content`` (imperative form), ``activeForm``
    (progressive form shown while running), and ``status`` (one of
    ``pending``, ``in_progress``, ``completed``). At most one item may be
    ``in_progress`` — extra ones are rejected by the validator.
    """

    class Input(BaseModel):
        todos: list[TodoItem] = Field(default_factory=list)

        @field_validator("todos")
        @classmethod
        def _at_most_one_in_progress(cls, v: list[TodoItem]) -> list[TodoItem]:
            in_progress = sum(1 for t in v if t.status == "in_progress")
            if in_progress > 1:
                raise ValueError("at most one task may be 'in_progress' at a time")
            return v

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, TodoWriteTool.Input)
        _TODO_STORE[_DEFAULT_SESSION] = list(args.todos)
        rendered = []
        for i, t in enumerate(args.todos, start=1):
            marker = {
                "pending": "[ ]",
                "in_progress": "[~]",
                "completed": "[x]",
            }[t.status]
            label = t.activeForm if t.status == "in_progress" else t.content
            rendered.append(f"{i}. {marker} {label}")
        body = "\n".join(rendered) or "<empty list>"
        return ToolResult(
            output=body,
            metadata={
                "session": _DEFAULT_SESSION,
                "total": len(args.todos),
                "in_progress": sum(1 for t in args.todos if t.status == "in_progress"),
                "completed": sum(1 for t in args.todos if t.status == "completed"),
            },
        )
