# Tools API

Classe base, decorator de registro, helpers e o schema de cada tool nativa.
Para o uso operacional (o que cada tool faz no dia-a-dia, com exemplos),
veja [Tools](../tools/index.md).

## Classe base, registry e helpers

::: vulpcode.tools.base
    options:
      heading_level: 3
      show_root_heading: false
      show_root_full_path: false
      members:
        - Tool
        - ToolResult
        - tool
        - TOOL_REGISTRY
        - get_tool
        - list_tools
        - execute_tool_call
        - clear_registry

## Tools nativas

Cada tool e uma classe com o decorator [`@tool`](#vulpcode.tools.base.tool).
A classe declara um nested ``Input`` (Pydantic) com os argumentos e
implementa ``async run``. Aqui estao apenas os schemas — para uso
operacional veja [Tools](../tools/index.md).

### Filesystem

#### ReadTool

::: vulpcode.tools.read.ReadTool
    options:
      heading_level: 5
      show_root_full_path: false

#### WriteTool

::: vulpcode.tools.write.WriteTool
    options:
      heading_level: 5
      show_root_full_path: false

#### EditTool

::: vulpcode.tools.edit.EditTool
    options:
      heading_level: 5
      show_root_full_path: false

#### MultiEditTool

::: vulpcode.tools.edit.MultiEditTool
    options:
      heading_level: 5
      show_root_full_path: false

### Busca

#### GlobTool

::: vulpcode.tools.glob.GlobTool
    options:
      heading_level: 5
      show_root_full_path: false

#### GrepTool

::: vulpcode.tools.grep.GrepTool
    options:
      heading_level: 5
      show_root_full_path: false

### Shell

#### BashTool

::: vulpcode.tools.bash.BashTool
    options:
      heading_level: 5
      show_root_full_path: false

#### BashOutputTool

::: vulpcode.tools.bash_background.BashOutputTool
    options:
      heading_level: 5
      show_root_full_path: false

#### KillBashTool

::: vulpcode.tools.bash_background.KillBashTool
    options:
      heading_level: 5
      show_root_full_path: false

### Web

#### WebFetchTool

::: vulpcode.tools.web.WebFetchTool
    options:
      heading_level: 5
      show_root_full_path: false

#### WebSearchTool

::: vulpcode.tools.web.WebSearchTool
    options:
      heading_level: 5
      show_root_full_path: false

### Agente

#### TaskTool

::: vulpcode.tools.task.TaskTool
    options:
      heading_level: 5
      show_root_full_path: false

### Produtividade

#### TodoWriteTool

::: vulpcode.tools.todo.TodoWriteTool
    options:
      heading_level: 5
      show_root_full_path: false

#### NotebookEditTool

::: vulpcode.tools.notebook.NotebookEditTool
    options:
      heading_level: 5
      show_root_full_path: false
