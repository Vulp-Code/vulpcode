"""/compact - summarize history to reduce token usage."""
from __future__ import annotations

from vulpcode.commands._base import SlashCommand
from vulpcode.providers.base import Message


class CompactCommand(SlashCommand):
    name = "compact"
    help_text = "Summarize the conversation history into a compact context"

    async def run(self, repl, args: str) -> None:
        agent = repl.agent
        if len(agent._messages) < 4:
            repl.renderer.console.print("[muted]history too short to compact[/]")
            return
        repl.renderer.console.print("[muted]requesting summary...[/]")
        summary_messages = list(agent._messages) + [
            Message(
                role="user",
                content=(
                    "Summarize the conversation so far in a single paragraph, "
                    "preserving any concrete file paths, decisions, or open TODOs. "
                    "No preamble, just the summary."
                ),
            ),
        ]
        text = ""
        try:
            async for chunk in agent.provider.stream(
                messages=summary_messages,
                tools=[],
                model=agent.model,
                system="You are a concise summarizer.",
            ):
                if chunk.type == "text" and chunk.delta:
                    text += chunk.delta
                elif chunk.type == "stop":
                    break
        except Exception as exc:
            repl.renderer.render_error(f"compact failed: {exc}")
            return
        agent._messages = [
            Message(role="user", content="<previous conversation summary>"),
            Message(role="assistant", content=text),
        ]
        repl.renderer.console.print("[green]history compacted[/]")
        repl.renderer.console.print(f"[muted]{text}[/]")
