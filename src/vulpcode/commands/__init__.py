"""Built-in slash commands."""
from vulpcode.commands._base import SlashCommand
from vulpcode.commands.compact import CompactCommand
from vulpcode.commands.cost import CostCommand
from vulpcode.commands.mcp_cmd import McpCommand
from vulpcode.commands.provider_model import ModelCommand, ProviderCommand
from vulpcode.commands.session_cmds import LoadCommand, SaveCommand
from vulpcode.commands.tools import ToolsCommand


def build_default_commands() -> dict[str, SlashCommand]:
    """All commands available in the REPL by default."""
    cmds: list[SlashCommand] = [
        ToolsCommand(),
        CostCommand(),
        CompactCommand(),
        ProviderCommand(),
        ModelCommand(),
        SaveCommand(),
        LoadCommand(),
        McpCommand(),
    ]
    return {c.name: c for c in cmds}


__all__ = [
    "SlashCommand",
    "ToolsCommand",
    "CostCommand",
    "CompactCommand",
    "ProviderCommand",
    "ModelCommand",
    "SaveCommand",
    "LoadCommand",
    "McpCommand",
    "build_default_commands",
]
