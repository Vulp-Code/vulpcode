"""Vulpcode middleware harness: hook bus + middleware registration."""
from __future__ import annotations

from typing import Any

from vulpcode.harness.hooks import HookBus
from vulpcode.harness.state import STATE_SCHEMA_VERSION, LoopState, StateMetadata

__all__ = [
    "HookBus",
    "LoopState",
    "StateMetadata",
    "STATE_SCHEMA_VERSION",
    "register_default_middleware",
    "list_middleware",
]


def _build_eviction_hook(cfg: Any) -> Any:
    from vulpcode.harness.eviction import EvictionConfig, evict_messages

    eviction_cfg = EvictionConfig(
        enabled=cfg.get("enabled", False),
        max_messages=cfg.get("max_messages", 200),
        max_tokens=cfg.get("max_tokens", None),
        keep_recent=cfg.get("keep_recent", 20),
        keep_first_system=cfg.get("keep_first_system", True),
        drop_strategy=cfg.get("drop_strategy", "oldest_pair"),
    )

    def hook(state: LoopState, **kwargs: Any) -> None:
        evict_messages(state, eviction_cfg)

    hook.name = "eviction"  # type: ignore[attr-defined]
    hook.reads = ("messages",)  # type: ignore[attr-defined]
    hook.writes = ("messages",)  # type: ignore[attr-defined]
    return hook


def _build_clip_hook(cfg: Any) -> Any:
    from vulpcode.harness.eviction import OverflowClipConfig, clip_tool_output

    clip_cfg = OverflowClipConfig(
        enabled=cfg.get("enabled", False),
        max_tool_output_chars=cfg.get("max_tool_output_chars", 8000),
        head_chars=cfg.get("head_chars", 4000),
        tail_chars=cfg.get("tail_chars", 1000),
    )

    def hook(state: LoopState, **kwargs: Any) -> Any:
        result = kwargs.get("result")
        call = kwargs.get("call")
        if result is None:
            return None
        return clip_tool_output(state, call=call, result=result, config=clip_cfg)

    hook.name = "overflow_clip"  # type: ignore[attr-defined]
    hook.reads = ()  # type: ignore[attr-defined]
    hook.writes = ()  # type: ignore[attr-defined]
    return hook


def register_default_middleware(
    bus: HookBus,
    config: dict,
    provider: Any = None,
    model: str = "",
    session_id: str = "default",
) -> None:
    """Register built-in middleware based on ``config``.

    Reads ``config["middleware"]["eviction"]``,
    ``config["middleware"]["overflow_clip"]``,
    ``config["middleware"]["summarization"]``, and
    ``config["middleware"]["context_hub"]``. Each section must have
    ``enabled = true`` to activate.  The overflow-clip settings can also
    live inside ``[middleware.eviction]`` as an alias when there is no
    separate ``[middleware.overflow_clip]`` section.

    Clip is registered **before** the context hub so that clip runs first:
    if an output is both large enough to clip and large enough to offload,
    clip reduces it first, then the hub decides whether it still needs offloading.

    Args:
        bus: The :class:`HookBus` to register hooks on.
        config: Fully resolved config dict (as returned by ``load_config``).
        provider: Optional provider instance. Required to activate the
            summarization hook.
        model: Model identifier forwarded to the summarization hook.
        session_id: Used as the sub-directory name for the context hub's
            handle storage.
    """
    middleware = config.get("middleware", {})
    eviction_raw: dict = middleware.get("eviction", {})
    # overflow_clip falls back to eviction section as alias
    overflow_clip_raw: dict = middleware.get("overflow_clip", eviction_raw)
    summarization_raw: dict = middleware.get("summarization", {})
    context_hub_raw: dict = middleware.get("context_hub", {})

    if eviction_raw.get("enabled", False):
        bus.register("before_iteration", _build_eviction_hook(eviction_raw))

    # Register clip BEFORE the context hub (clip reduces first, hub offloads residual).
    if overflow_clip_raw.get("enabled", False):
        bus.register("after_tool_call", _build_clip_hook(overflow_clip_raw))

    if summarization_raw.get("enabled", False) and provider is not None:
        from vulpcode.harness.summarization import SummarizationConfig, SummarizationHook

        summ_cfg = SummarizationConfig(
            enabled=summarization_raw.get("enabled", False),
            trigger_at_tokens=summarization_raw.get("trigger_at_tokens", 60000),
            keep_recent_messages=summarization_raw.get("keep_recent_messages", 20),
            target_tokens=summarization_raw.get("target_tokens", 8000),
            cooldown_iterations=summarization_raw.get("cooldown_iterations", 5),
            summary_model=summarization_raw.get("summary_model", ""),
        )
        hook = SummarizationHook(summ_cfg, provider, model=model)
        bus.register("before_iteration", hook)

    if context_hub_raw.get("enabled", False):
        from pathlib import Path

        from vulpcode.harness.context_hub import ContextHub, ContextHubConfig
        from vulpcode.tools.handle import set_hub

        hub_cfg = ContextHubConfig(
            enabled=True,
            threshold_chars=context_hub_raw.get("threshold_chars", 4000),
            preview_head_lines=context_hub_raw.get("preview_head_lines", 30),
            preview_tail_lines=context_hub_raw.get("preview_tail_lines", 10),
            storage_dir=Path(
                context_hub_raw.get("storage_dir", "~/.vulpcode/handles")
            ),
            keep_handles_days=context_hub_raw.get("keep_handles_days", 7),
        )
        hub = ContextHub(hub_cfg, session_id)
        set_hub(hub)
        bus.register("after_tool_call", hub)

    tool_patch_raw: dict = middleware.get("tool_patch", {})
    if tool_patch_raw.get("enabled", False):
        from vulpcode.harness.tool_patch import ToolPatchConfig, ToolPatcher, _compile_rules

        tp_cfg = ToolPatchConfig(
            enabled=True,
            rules=_compile_rules(tool_patch_raw.get("rules", [])),
        )
        bus.register("before_tool_call", ToolPatcher(tp_cfg))

    skills_raw: dict = config.get("skills", {})
    if skills_raw.get("enabled", False):
        from pathlib import Path as _Path

        import vulpcode.session as _session_module
        from vulpcode.harness.skills import SkillRegistry, SkillsConfig

        raw_dirs = skills_raw.get("search_dirs", [])
        if raw_dirs:
            skills_cfg = SkillsConfig(
                enabled=True, search_dirs=[_Path(d) for d in raw_dirs]
            )
        else:
            skills_cfg = SkillsConfig(enabled=True)

        registry = SkillRegistry(skills_cfg)
        if registry.all():
            bus.register("before_send", registry)
            _session_module.skill_registry = registry
            from vulpcode.harness.skills import enforce_skill_tool_filter

            bus.register("before_tool_call", enforce_skill_tool_filter)


def list_middleware(bus: HookBus) -> str:
    """Format registered middleware as a human-readable string."""
    description = bus.describe()
    if not description:
        return "No middleware registered."
    lines = ["Registered middleware (by event):\n"]
    for event, hooks in sorted(description.items()):
        lines.append(f"{event}:")
        for h in hooks:
            reads_str = ", ".join(h["reads"]) if h["reads"] else "(none)"
            writes_str = ", ".join(h["writes"]) if h["writes"] else "(none)"
            lines.append(f"  - {h['name']}  reads=({reads_str})  writes=({writes_str})")
        lines.append("")
    return "\n".join(lines)
