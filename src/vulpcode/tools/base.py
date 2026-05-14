"""Tool ABC, registry, and the ``@tool`` decorator.

Every native capability the agent can invoke (Read, Write, Bash, ...) is a
:class:`Tool` subclass declared in a sibling module and registered via the
:func:`tool` decorator. The agent loop:

1. Calls :meth:`Tool.to_schema` on every registered tool to build the
   provider-bound tool list.
2. Receives :class:`~vulpcode.providers.base.ToolCall` events from the
   provider stream.
3. Dispatches each call through :func:`execute_tool_call`, which validates
   the arguments against ``Tool.Input`` and runs the tool's ``run``.

External code wanting to add a custom tool only needs to subclass
:class:`Tool`, declare ``Input``, implement ``run``, and apply ``@tool``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from vulpcode.providers.base import ToolCall


class ToolResult(BaseModel):
    """Result returned by a tool execution.

    The agent loop converts this back into a ``role="tool"`` message for the
    next provider turn.

    Attributes:
        output: Successful output as text. Becomes the tool message content
            when ``is_error`` is ``False``.
        error: Error description when ``is_error`` is ``True``. May be ``None``
            even on errors — fall back to ``output`` in that case.
        is_error: Whether the call failed. Errors are still surfaced to the
            model so it can react, rather than aborting the loop.
        metadata: Free-form structured data the tool wants to attach (e.g.
            counts, file paths, exit codes). Not sent to the model — used by
            the UI / logs.
    """

    output: str = ""
    error: str | None = None
    is_error: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_string(self) -> str:
        """Render the result for inclusion in the next LLM turn.

        Returns:
            ``"Error: <msg>"`` when ``is_error`` is ``True``, otherwise the
            raw :attr:`output`.
        """
        if self.is_error:
            return f"Error: {self.error or self.output}"
        return self.output


class Tool(ABC):
    """Abstract base class for native tools.

    A concrete tool MUST:

    1. Declare a nested ``class Input(BaseModel): ...`` with the args schema.
       This drives both validation and the JSON Schema sent to the model.
    2. Implement ``async run(self, args: Input) -> ToolResult``.
    3. Be registered with the :func:`tool` decorator (which sets the class
       attributes :attr:`_tool_name`, :attr:`_tool_description`,
       :attr:`_requires_confirm`).

    Attributes:
        Input: Pydantic model describing the tool's arguments.

    Example:
        >>> from pydantic import BaseModel
        >>> @tool(name="echo", description="Echo back the message.")
        ... class EchoTool(Tool):
        ...     class Input(BaseModel):
        ...         message: str
        ...     async def run(self, args: "EchoTool.Input") -> ToolResult:
        ...         return ToolResult(output=args.message)
    """

    _tool_name: str
    _tool_description: str
    _requires_confirm: bool

    Input: type[BaseModel]

    @abstractmethod
    async def run(self, args: BaseModel) -> ToolResult:
        """Execute the tool with validated arguments.

        Args:
            args: Instance of the tool's ``Input`` model.

        Returns:
            A :class:`ToolResult` carrying ``output`` (success) or ``error``
            with ``is_error=True`` (failure).
        """

    @classmethod
    def to_schema(cls) -> dict[str, Any]:
        """Return the canonical tool schema understood by ``Provider.stream``.

        The shape is provider-agnostic — each :class:`Provider` adapter
        translates it to its own native tool format.

        Returns:
            A dict with ``name``, ``description``, and ``input_schema`` (a
            JSON Schema derived from ``Input``).
        """
        return {
            "name": cls._tool_name,
            "description": cls._tool_description,
            "input_schema": cls.Input.model_json_schema(),
        }

    @classmethod
    def parse_args(cls, raw: dict[str, Any]) -> BaseModel:
        """Validate and coerce a raw arguments dict into the ``Input`` model.

        Args:
            raw: Raw arguments dict (typically from a
                :class:`~vulpcode.providers.base.ToolCall`).

        Returns:
            A validated ``Input`` instance.

        Raises:
            pydantic.ValidationError: If ``raw`` does not conform to ``Input``.
        """
        return cls.Input.model_validate(raw)


TOOL_REGISTRY: dict[str, type[Tool]] = {}
"""Global registry mapping tool name → :class:`Tool` subclass.

Populated by the :func:`tool` decorator. Iteration order is insertion order,
which is also the order shown to the model in the tool list.
"""


def tool(
    *,
    name: str,
    description: str,
    requires_confirm: bool = False,
) -> Callable[[type[Tool]], type[Tool]]:
    """Class decorator that registers a :class:`Tool` subclass.

    The decorator validates the class shape (must subclass :class:`Tool`,
    must declare a nested ``Input`` :class:`pydantic.BaseModel`) and stores
    metadata on the class.

    Args:
        name: Globally unique tool name. Must not already exist in
            :data:`TOOL_REGISTRY`.
        description: Short description sent to the model alongside the
            schema. Make it concrete — the model uses this to decide when
            to invoke the tool.
        requires_confirm: When ``True``, the runtime asks the user to confirm
            before executing this tool (used by destructive operations like
            ``Bash`` or ``Write`` in the default permission mode).

    Returns:
        A decorator that registers the class and returns it unchanged.

    Raises:
        TypeError: If the decorated object is not a :class:`Tool` subclass,
            or if it does not declare a nested ``Input`` BaseModel.
        ValueError: If ``name`` is already registered.

    Example:
        >>> @tool(name="ping", description="Reply with pong.")
        ... class PingTool(Tool):
        ...     class Input(BaseModel):
        ...         pass
        ...     async def run(self, args):
        ...         return ToolResult(output="pong")
    """

    def decorator(cls: type[Tool]) -> type[Tool]:
        if not isinstance(cls, type) or not issubclass(cls, Tool):
            raise TypeError(f"@tool can only decorate Tool subclasses, got {cls!r}")
        if not hasattr(cls, "Input"):
            raise TypeError(f"{cls.__name__}: @tool requires a nested 'Input' BaseModel")
        input_cls = cls.Input
        if not isinstance(input_cls, type) or not issubclass(input_cls, BaseModel):
            raise TypeError(
                f"{cls.__name__}: @tool requires a nested 'Input' BaseModel"
            )
        cls._tool_name = name
        cls._tool_description = description
        cls._requires_confirm = requires_confirm
        if name in TOOL_REGISTRY:
            raise ValueError(f"Tool name {name!r} already registered")
        TOOL_REGISTRY[name] = cls
        return cls

    return decorator


def get_tool(name: str) -> type[Tool]:
    """Look up a tool class by registered name.

    Args:
        name: Tool name, as passed to :func:`tool`.

    Returns:
        The :class:`Tool` subclass.

    Raises:
        KeyError: If ``name`` is not registered.

    Example:
        >>> get_tool("read").__name__
        'ReadTool'
    """
    if name not in TOOL_REGISTRY:
        raise KeyError(f"Tool not found: {name!r}")
    return TOOL_REGISTRY[name]


def list_tools() -> list[type[Tool]]:
    """Return all registered tool classes in registration order.

    Returns:
        List of :class:`Tool` subclasses.
    """
    return list(TOOL_REGISTRY.values())


def clear_registry() -> None:
    """Test-only helper: empty the global tool registry.

    Useful in tests that want to register a custom tool without leaking it
    into other tests. Production code should not call this.
    """
    TOOL_REGISTRY.clear()


async def execute_tool_call(
    tool_call: ToolCall,
    *,
    allow_unknown: bool = False,
) -> ToolResult:
    """Execute a tool by name with the given arguments.

    Looks up the tool in :data:`TOOL_REGISTRY`, validates ``tool_call.arguments``
    against its ``Input`` schema, and runs ``tool.run``. Both validation and
    runtime errors are converted to a :class:`ToolResult` with
    ``is_error=True`` so the agent loop can keep going.

    Args:
        tool_call: The :class:`~vulpcode.providers.base.ToolCall` emitted by
            the provider stream.
        allow_unknown: When ``True``, missing tools return an error result
            instead of raising. Useful when tolerating MCP-only tool names
            that aren't in the native registry.

    Returns:
        A :class:`ToolResult`. On invalid arguments or runtime errors,
        ``is_error`` is ``True`` and ``error`` describes the failure.

    Raises:
        KeyError: If the tool is not registered and ``allow_unknown`` is
            ``False``.
    """
    name = tool_call.name
    if name not in TOOL_REGISTRY:
        if allow_unknown:
            return ToolResult(error=f"Unknown tool: {name}", is_error=True)
        raise KeyError(f"Unknown tool: {name}")
    cls = TOOL_REGISTRY[name]
    instance = cls()
    try:
        args = cls.parse_args(tool_call.arguments or {})
    except Exception as exc:
        return ToolResult(error=f"Invalid arguments: {exc}", is_error=True)
    try:
        return await instance.run(args)
    except Exception as exc:
        return ToolResult(error=f"{type(exc).__name__}: {exc}", is_error=True)
