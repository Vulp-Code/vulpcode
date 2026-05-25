"""Tool-call interceptor: redact, block, or log-only based on configurable rules."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from vulpcode.providers.base import ToolCall

logger = logging.getLogger("vulpcode.harness.tool_patch")


@dataclass
class PatchRule:
    tool: str
    match: dict[str, re.Pattern]  # type: ignore[type-arg]
    action: Literal["redact", "block", "log_only"]
    replace: str = ""
    message: str = ""


@dataclass
class ToolPatchConfig:
    enabled: bool = False
    rules: list[PatchRule] = field(default_factory=list)


def _compile_rules(raw_rules: list[dict]) -> list[PatchRule]:
    """Parse raw rule dicts (from TOML) into PatchRule instances.

    Raises ValueError with a clear message if any regex pattern is syntactically
    invalid.  Validation happens at load time, not at call time.
    """
    rules: list[PatchRule] = []
    for i, raw in enumerate(raw_rules):
        tool: str = raw.get("tool", "*")
        action: str = raw.get("action", "log_only")
        replace: str = raw.get("replace", "")
        message: str = raw.get("message", "")
        raw_match: dict[str, str] = raw.get("match", {})

        compiled_match: dict[str, re.Pattern] = {}  # type: ignore[type-arg]
        for arg_name, pattern_str in raw_match.items():
            try:
                compiled_match[arg_name] = re.compile(pattern_str, re.MULTILINE)
            except re.error as exc:
                raise ValueError(
                    f"Invalid regex in tool_patch rule #{i} (arg={arg_name!r}): {exc}"
                ) from exc

        rules.append(
            PatchRule(
                tool=tool,
                match=compiled_match,
                action=action,  # type: ignore[arg-type]
                replace=replace,
                message=message,
            )
        )
    return rules


class ToolPatcher:
    """before_tool_call hook: applies redact, block, or log_only rules to tool calls.

    Returns:
        - A new ``ToolCall`` with patched arguments when ``action="redact"`` matches.
        - ``False`` when ``action="block"`` matches (caller injects an is_error
          tool result using the ``message`` stored in ``state.metadata["last_block_message"]``).
        - The original ``call`` when no rule matches or ``action="log_only"``.
    """

    name = "tool_patcher"
    reads: tuple[str, ...] = ("metadata",)
    writes: tuple[str, ...] = ("metadata",)

    def __init__(self, config: ToolPatchConfig) -> None:
        self._config = config

    def __call__(self, state: Any, *, call: ToolCall, **kwargs: Any) -> ToolCall | bool:
        if not self._config.enabled:
            return call

        for rule_idx, rule in enumerate(self._config.rules):
            # --- tool name filter ---
            if rule.tool != "*" and rule.tool != call.name:
                continue

            # --- argument match ---
            matched_fields: dict[str, str] = {}

            if "*" in rule.match:
                # Wildcard arg: test pattern against every argument value (stringified).
                pattern = rule.match["*"]
                for arg_name, arg_val in call.arguments.items():
                    val_str = str(arg_val)
                    if pattern.search(val_str):
                        matched_fields[arg_name] = val_str
            else:
                for arg_name, pattern in rule.match.items():
                    val = call.arguments.get(arg_name)
                    if val is None:
                        continue
                    val_str = str(val)
                    if pattern.search(val_str):
                        matched_fields[arg_name] = val_str

            if not matched_fields:
                continue

            # --- apply action ---
            if rule.action == "block":
                logger.info(
                    "[block] %s %s: blocked by rule #%d",
                    call.name,
                    ", ".join(f"{k}={v!r}" for k, v in matched_fields.items()),
                    rule_idx,
                )
                state.metadata["last_block_message"] = rule.message
                return False

            if rule.action == "redact":
                new_args = dict(call.arguments)
                total_subs = 0
                for arg_name in matched_fields:
                    if "*" in rule.match:
                        pattern = rule.match["*"]
                    else:
                        pattern = rule.match[arg_name]
                    original = str(new_args.get(arg_name, ""))
                    new_val, n = pattern.subn(rule.replace, original)
                    new_args[arg_name] = new_val
                    total_subs += n

                first_pattern = next(iter(rule.match.values())).pattern if rule.match else ""
                logger.info(
                    "[redact] %s %s: substituted %d occurrence(s) of /%s/",
                    call.name,
                    ", ".join(matched_fields.keys()),
                    total_subs,
                    first_pattern,
                )
                return ToolCall(id=call.id, name=call.name, arguments=new_args)

            if rule.action == "log_only":
                logger.warning(
                    "[log_only] %s %s: tool_patch matched but action=log_only (rule #%d)",
                    call.name,
                    ", ".join(f"{k}={v!r}" for k, v in matched_fields.items()),
                    rule_idx,
                )
                return call

        return call
