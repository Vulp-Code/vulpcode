"""Tool execution permission system."""
from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from vulpcode.providers import ToolCall
from vulpcode.tools import Tool


class Mode(StrEnum):
    """Permission modes that govern when the user must approve a tool call.

    Attributes:
        DEFAULT: Prompt the user only for tools whose
            ``Tool._requires_confirm`` flag is ``True`` (typically write/exec).
            Read-only tools run silently. This is the safe default for
            interactive use.
        AUTO: Allow every tool with no prompts. Suitable for trusted automation
            (CI, scripted runs).
        SAFE: Prompt for **every** tool, regardless of its
            ``_requires_confirm`` flag. Use when reviewing a sensitive task.
        PLAN: Refuse to execute any tool — the agent can think and write text
            but cannot touch the filesystem, shell, or network.
    """

    DEFAULT = "default"
    AUTO = "auto"
    SAFE = "safe"
    PLAN = "plan"


@dataclass
class PermissionDecision:
    """Outcome of a permission check for a single tool call.

    Attributes:
        allow: ``True`` if the agent may execute the tool.
        requires_prompt: ``True`` if the user was actually prompted (used by
            the UI to know whether to redraw after stdin input).
        reason: Short human-readable explanation
            (e.g. ``"auto mode"``, ``"user approved always"``,
            ``"plan mode (no execution)"``).
    """

    allow: bool
    requires_prompt: bool
    reason: str


PrompterFn = Callable[[str, dict], Awaitable[str]]
"""Async callable used by :class:`PermissionManager` to ask the user.

Signature: ``async (message: str, ctx: dict) -> str``. ``ctx`` carries
``{"name": tool_name, "arguments": tool_args}``. Must return one of
``"y"`` (allow once), ``"a"`` (allow always for this tool name), or
``"n"`` (deny).
"""


async def stdin_prompter(message: str, ctx: dict) -> str:
    """Default prompter: read ``y``/``a``/``n`` from stdin without blocking the loop.

    The synchronous ``sys.stdin.readline`` call is dispatched to the default
    executor so other coroutines keep running.

    Args:
        message: Human-readable prompt (e.g. ``"Tool 'Bash' wants to run."``).
        ctx: Context dict; the keys ``"name"`` and ``"arguments"`` are
            displayed to help the user judge the call.

    Returns:
        ``"y"``, ``"a"``, or ``"n"``. Any other input is coerced to ``"n"``.
    """
    print(f"\n[permission] {message}")
    print("Tool args:", ctx.get("arguments"))
    print("[y] yes once  [a] always for this tool  [n] no")
    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(None, sys.stdin.readline)
    answer = (answer or "n").strip().lower()[:1]
    if answer not in {"y", "a", "n"}:
        return "n"
    return answer


class PermissionManager:
    """Decides whether a tool call may run, prompting the user if needed.

    The :class:`~vulpcode.agent.Agent` calls :meth:`check` for every tool the
    model requests. The decision depends on the active :class:`Mode`, on the
    tool class's ``_requires_confirm`` flag, and on the session allowlist
    (built from ``config["permissions"]["always_allow_tools"]`` plus any tool
    the user approved with ``"a"`` during the session).

    Args:
        config: Loaded config dict (typically the result of
            :func:`vulpcode.config.load_config`). Only
            ``config["permissions"]["always_allow_tools"]`` is consulted; the
            rest is kept on ``self.config`` for callers that need it.
        mode: The active :class:`Mode`. Defaults to :attr:`Mode.DEFAULT`.
        prompter: Async callable invoked when user approval is needed.
            Defaults to :func:`stdin_prompter`. Replace it to integrate with a
            TUI/web UI — see ``Custom prompter`` in the API docs.
    """

    def __init__(
        self,
        config: dict,
        mode: Mode = Mode.DEFAULT,
        prompter: PrompterFn | None = None,
    ) -> None:
        self.config = config
        self.mode = mode
        self.prompter: PrompterFn = prompter or stdin_prompter
        permissions_cfg = (config.get("permissions", {}) or {}) if config else {}
        always_allow = permissions_cfg.get("always_allow_tools", []) or []
        self._session_allowlist: set[str] = set(always_allow)

    async def check(
        self, tool_call: ToolCall, tool_cls: type[Tool]
    ) -> PermissionDecision:
        """Evaluate whether ``tool_call`` may execute given the current mode.

        Decision order:

        1. :attr:`Mode.AUTO` -> always allow.
        2. :attr:`Mode.PLAN` -> always deny.
        3. Otherwise compute ``requires`` from the tool class
           (always ``True`` under :attr:`Mode.SAFE`).
        4. If no confirmation is required, allow.
        5. If the tool name is in the session allowlist, allow.
        6. Call the prompter and map ``y``/``a``/``n`` to allow-once,
           allow-always-and-remember, or deny.

        Args:
            tool_call: The :class:`~vulpcode.providers.base.ToolCall` issued
                by the model.
            tool_cls: The concrete :class:`~vulpcode.tools.base.Tool` subclass
                that would handle the call (its ``_requires_confirm`` flag is
                consulted).

        Returns:
            A :class:`PermissionDecision` with ``allow``, ``requires_prompt``,
            and a human-readable ``reason``.
        """
        if self.mode == Mode.AUTO:
            return PermissionDecision(True, False, "auto mode")
        if self.mode == Mode.PLAN:
            return PermissionDecision(False, False, "plan mode (no execution)")

        requires = tool_cls._requires_confirm
        if self.mode == Mode.SAFE:
            requires = True

        if not requires:
            return PermissionDecision(True, False, "no confirmation needed")

        if tool_call.name in self._session_allowlist:
            return PermissionDecision(True, False, "session allowlist")

        msg = f"Tool {tool_call.name!r} wants to run."
        ctx = {"name": tool_call.name, "arguments": tool_call.arguments}
        try:
            answer = await self.prompter(msg, ctx)
        except Exception:
            return PermissionDecision(False, False, "prompt failed")

        if answer == "y":
            return PermissionDecision(True, True, "user approved once")
        if answer == "a":
            self._session_allowlist.add(tool_call.name)
            return PermissionDecision(True, True, "user approved always")
        return PermissionDecision(False, True, "user rejected")
