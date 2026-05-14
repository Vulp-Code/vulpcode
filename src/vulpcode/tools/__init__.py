"""Native tools and the tool registry."""
from vulpcode.tools.base import (
    TOOL_REGISTRY,
    Tool,
    ToolResult,
    clear_registry,
    execute_tool_call,
    get_tool,
    list_tools,
    tool,
)

__all__ = [
    "TOOL_REGISTRY",
    "Tool",
    "ToolResult",
    "TodoItem",
    "clear_registry",
    "clear_todos",
    "execute_tool_call",
    "get_tool",
    "get_todos",
    "list_tools",
    "tool",
]

from vulpcode.tools import read as _read  # noqa: E402, F401  (registers ReadTool)
from vulpcode.tools import write as _write  # noqa: E402, F401  (registers WriteTool)
from vulpcode.tools import edit as _edit  # noqa: E402, F401  (registers Edit, MultiEdit)
from vulpcode.tools import glob as _glob  # noqa: E402, F401  (registers GlobTool)
from vulpcode.tools import grep as _grep  # noqa: E402, F401  (registers GrepTool)
from vulpcode.tools import bash as _bash  # noqa: E402, F401  (registers BashTool)
from vulpcode.tools import bash_background as _bash_bg  # noqa: E402, F401  (registers BashOutput, KillBash)
from vulpcode.tools import web as _web  # noqa: E402, F401  (registers WebFetch, WebSearch)
from vulpcode.tools import todo as _todo  # noqa: E402, F401  (registers TodoWriteTool)
from vulpcode.tools.todo import TodoItem, clear_todos, get_todos  # noqa: E402, F401
from vulpcode.tools import task as _task  # noqa: E402, F401  (registers TaskTool)
from vulpcode.tools import notebook as _notebook  # noqa: E402, F401  (registers NotebookEditTool)
