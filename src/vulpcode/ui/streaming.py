"""Connect Agent events to the Renderer."""
from __future__ import annotations

from rich.live import Live
from rich.spinner import Spinner

from vulpcode.agent import (
    Agent,
    ErrorEvent,
    TextEvent,
    ToolDeniedEvent,
    ToolEndEvent,
    ToolStartEvent,
    TurnEndEvent,
    UsageEvent,
)
from vulpcode.ui.render import Renderer


async def stream_agent_turn(
    agent: Agent,
    user_input: str,
    renderer: Renderer,
    spinner: bool = True,
) -> None:
    """Consume Agent.turn(user_input) and render each event."""
    console = renderer.console
    live: Live | None = None

    def start_spinner(msg: str) -> None:
        nonlocal live
        if not spinner:
            return
        if live is not None:
            return
        live = Live(
            Spinner("dots", text=msg),
            console=console,
            refresh_per_second=10,
            transient=True,
        )
        live.start()

    def stop_spinner() -> None:
        nonlocal live
        if live is not None:
            live.stop()
            live = None

    # Install a spinner-aware prompter on the agent's permission manager so the
    # spinner doesn't fight stdin when the user is asked to confirm a tool.
    permissions = getattr(agent, "permissions", None)
    original_prompter = getattr(permissions, "prompter", None) if permissions else None

    if permissions is not None and original_prompter is not None:
        async def _spinner_aware_prompter(msg: str, ctx: dict) -> str:
            stop_spinner()
            try:
                return await original_prompter(msg, ctx)
            finally:
                start_spinner("Thinking...")

        permissions.prompter = _spinner_aware_prompter

    try:
        start_spinner("Thinking...")
        async for ev in agent.turn(user_input):
            if isinstance(ev, TextEvent):
                stop_spinner()
                renderer.render_text_chunk(ev.text)
            elif isinstance(ev, ToolStartEvent):
                stop_spinner()
                renderer.render_tool_start(ev.tool_call)
                start_spinner(f"Running {ev.tool_call.name}...")
            elif isinstance(ev, ToolEndEvent):
                stop_spinner()
                renderer.render_tool_end(ev.tool_call, ev.result)
                start_spinner("Thinking...")
            elif isinstance(ev, ToolDeniedEvent):
                stop_spinner()
                renderer.render_tool_denied(ev.tool_call, ev.reason)
                start_spinner("Thinking...")
            elif isinstance(ev, UsageEvent):
                renderer.render_usage(ev.usage)
            elif isinstance(ev, ErrorEvent):
                stop_spinner()
                renderer.render_error(ev.error)
            elif isinstance(ev, TurnEndEvent):
                stop_spinner()
                renderer.render_turn_end(ev.stop_reason)
                return
    finally:
        stop_spinner()
        if permissions is not None and original_prompter is not None:
            permissions.prompter = original_prompter
