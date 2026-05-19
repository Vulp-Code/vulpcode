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
from vulpcode.tools import write_py as _write_py  # noqa: E402, F401  (registers WritePy)
from vulpcode.tools import write_ipynb as _write_ipynb  # noqa: E402, F401  (registers WriteIpynb)
from vulpcode.tools import write_md as _write_md  # noqa: E402, F401  (registers WriteMd)
from vulpcode.tools import write_docx as _write_docx  # noqa: E402, F401  (registers WriteDocx)
from vulpcode.tools import write_pdf as _write_pdf  # noqa: E402, F401  (registers WritePdf)
from vulpcode.tools import write_json as _write_json  # noqa: E402, F401  (registers WriteJson)
from vulpcode.tools import write_yaml as _write_yaml  # noqa: E402, F401  (registers WriteYaml)
from vulpcode.tools import write_toml as _write_toml  # noqa: E402, F401  (registers WriteToml)
from vulpcode.tools import write_csv as _write_csv  # noqa: E402, F401  (registers WriteCsv)
from vulpcode.tools import write_xml as _write_xml  # noqa: E402, F401  (registers WriteXml)
from vulpcode.tools import write_html as _write_html  # noqa: E402, F401  (registers WriteHtml)
from vulpcode.tools import write_sh as _write_sh  # noqa: E402, F401  (registers WriteSh)
from vulpcode.tools import write_sql as _write_sql  # noqa: E402, F401  (registers WriteSql)
from vulpcode.tools import write_svg as _write_svg  # noqa: E402, F401  (registers WriteSvg)
from vulpcode.tools import write_dot as _write_dot  # noqa: E402, F401  (registers WriteDot)
