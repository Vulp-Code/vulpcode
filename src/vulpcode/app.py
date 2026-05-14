"""REPL bootstrap: builds Agent, Renderer, Repl from config."""
from __future__ import annotations

from rich.console import Console

import vulpcode.tools  # noqa: F401  (force tool registration)
from vulpcode.agent import Agent
from vulpcode.commands import build_default_commands
from vulpcode.config import load_config
from vulpcode.mcp import start_configured_servers, stop_servers
from vulpcode.permissions import Mode, PermissionManager
from vulpcode.providers import build_provider
from vulpcode.tools import list_tools
from vulpcode.ui import Renderer, get_theme
from vulpcode.ui.repl import Repl


def _make_permissions(config: dict, cli_overrides: dict) -> PermissionManager:
    if cli_overrides.get("auto"):
        mode = Mode.AUTO
    elif cli_overrides.get("safe"):
        mode = Mode.SAFE
    elif cli_overrides.get("plan"):
        mode = Mode.PLAN
    else:
        mode = Mode.DEFAULT
    return PermissionManager(config=config, mode=mode)


def _cfg_overrides_from_cli(o: dict) -> dict:
    overrides: dict = {}
    if o.get("provider"):
        overrides["default_provider"] = o["provider"]
    if o.get("model"):
        overrides["default_model"] = o["model"]
    return overrides


def _default_model_for(provider_name: str) -> str:
    return {
        "anthropic": "claude-sonnet-4-6",
        "openai": "gpt-4o-mini",
        "deepseek": "deepseek-chat",
        "groq": "llama-3.1-70b-versatile",
        "openrouter": "openrouter/auto",
        "gemini": "gemini-2.5-pro",
        "ollama": "qwen2.5-coder:7b",
        "lmstudio": "local-model",
        "vllm": "local-model",
        "internal-llm": "internal-llm",
    }.get(provider_name, "")


async def start_repl(
    *,
    cli_overrides: dict | None = None,
    one_shot: str | None = None,
    print_mode: bool = False,
    resume: bool = False,
) -> int:
    """Build dependencies and start the REPL or one-shot run.

    Returns: process exit code.
    """
    cli_overrides = cli_overrides or {}
    cfg = load_config(cli_overrides=_cfg_overrides_from_cli(cli_overrides))

    provider_name = cfg.get("default_provider", "anthropic")
    model = cfg.get("default_model") or _default_model_for(provider_name)
    provider_cfg = (cfg.get("providers", {}) or {}).get(provider_name, {})
    provider = build_provider(provider_name, provider_cfg)

    tool_classes = list_tools()
    tools = [cls() for cls in tool_classes]

    permissions = _make_permissions(cfg, cli_overrides)

    console = Console(force_terminal=not print_mode, no_color=False)
    theme = get_theme(cfg.get("ui", {}).get("theme", "default"))
    renderer = Renderer(console, theme)

    agent = Agent(
        provider=provider,
        tools=tools,
        model=model,
        permissions=permissions,
        model_settings=cfg.get("model_settings", {}) or {},
    )

    repl = Repl(
        agent=agent,
        renderer=renderer,
        config=cfg,
        commands=build_default_commands(),
    )

    mcp_servers = await start_configured_servers(cfg)
    for s in mcp_servers:
        for tcls in s.tool_classes:
            agent.tools[tcls._tool_name] = tcls()

    if resume:
        from vulpcode.session import latest_session_name, load_session

        last = latest_session_name()
        if last:
            try:
                load_session(last, agent)
                renderer.console.print(f"[green]resumed session {last}[/]")
            except Exception as exc:
                renderer.render_error(f"resume failed: {exc}")
        else:
            renderer.console.print("[yellow]no saved session to resume[/]")

    try:
        if one_shot is not None:
            await repl.one_shot(one_shot)
            return 0
        await repl.run()
        return 0
    finally:
        await stop_servers(mcp_servers)
