# Tarefa 02.02 - Tool ABC + Decorator + Registry

**Status**: PENDENTE
**Fase**: 02 - Nucleo
**Dependencias**: 02.01 (provider base com tipos canonicos)
**Bloqueia**: FASE 04, 05, 06 (todas as tools)

---

## Objetivo

Definir a base de tools: classe abstrata `Tool`, decorator `@tool` para registro
declarativo, classe de resultado `ToolResult` e o registro global `TOOL_REGISTRY`
em `src/vulpcode/tools/base.py`. Isto e o que cada tool concreta (Bash, Read,
Write, etc.) ira herdar.

---

## Descricao Tecnica

**Arquivo a criar**: `/home/guhaase/projetos/vulpcode/src/vulpcode/tools/base.py`

### Resultado de tool

```python
class ToolResult(BaseModel):
    """Result returned by a tool execution."""
    output: str = ""              # primary stdout-like content
    error: str | None = None      # error message (if failed)
    is_error: bool = False        # True iff this result represents a failure
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_string(self) -> str:
        """Render the result for inclusion in the next LLM turn."""
        if self.is_error:
            return f"Error: {self.error or self.output}"
        return self.output
```

### Tool ABC

```python
class Tool(ABC):
    """Abstract base class for native tools.

    Subclasses MUST:
    - declare a nested ``class Input(BaseModel): ...`` with the args schema.
    - implement async ``run(self, args: Input) -> ToolResult``.
    - register via the @tool decorator.
    """

    # Set by @tool decorator
    _tool_name: str
    _tool_description: str
    _requires_confirm: bool

    Input: type[BaseModel]  # nested class declared by subclass

    @abstractmethod
    async def run(self, args: BaseModel) -> ToolResult: ...

    @classmethod
    def to_schema(cls) -> dict[str, Any]:
        """Return the canonical tool schema understood by Provider.stream()."""
        return {
            "name": cls._tool_name,
            "description": cls._tool_description,
            "input_schema": cls.Input.model_json_schema(),
        }

    @classmethod
    def parse_args(cls, raw: dict[str, Any]) -> BaseModel:
        """Validate and coerce raw dict into the Input model."""
        return cls.Input.model_validate(raw)
```

### Decorator + Registry

```python
TOOL_REGISTRY: dict[str, type[Tool]] = {}


def tool(
    *,
    name: str,
    description: str,
    requires_confirm: bool = False,
) -> Callable[[type[Tool]], type[Tool]]:
    """Class decorator: registers a Tool subclass in the global registry."""

    def decorator(cls: type[Tool]) -> type[Tool]:
        if not issubclass(cls, Tool):
            raise TypeError(f"@tool can only decorate Tool subclasses, got {cls!r}")
        if not hasattr(cls, "Input"):
            raise TypeError(f"{cls.__name__}: @tool requires a nested 'Input' BaseModel")
        cls._tool_name = name
        cls._tool_description = description
        cls._requires_confirm = requires_confirm
        if name in TOOL_REGISTRY:
            raise ValueError(f"Tool name {name!r} already registered")
        TOOL_REGISTRY[name] = cls
        return cls

    return decorator


def get_tool(name: str) -> type[Tool]:
    """Lookup a tool class by registered name."""
    if name not in TOOL_REGISTRY:
        raise KeyError(f"Tool not found: {name!r}")
    return TOOL_REGISTRY[name]


def list_tools() -> list[type[Tool]]:
    """All registered tool classes, in registration order."""
    return list(TOOL_REGISTRY.values())


def clear_registry() -> None:
    """Test-only helper: empties the registry."""
    TOOL_REGISTRY.clear()
```

### Helper para o Agente

Adicionar tambem helpers usados pelo agent loop:

```python
async def execute_tool_call(
    tool_call: "ToolCall",
    *,
    allow_unknown: bool = False,
) -> ToolResult:
    """Execute a tool by name with the given arguments.

    Imports ToolCall lazily to avoid circular dep with providers.base.
    """
    from vulpcode.providers.base import ToolCall  # noqa: F401  (type-only at runtime)

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
```

### Atualizar `tools/__init__.py`

```python
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
    "clear_registry",
    "execute_tool_call",
    "get_tool",
    "list_tools",
    "tool",
]
```

---

## INSTRUCAO CRITICA

- Tools NAO sao registradas automaticamente — apenas quando o modulo da tool e
  importado. As fases 04-06 cuidarao do import (via `tools/__init__.py` ou via
  modulo de bootstrap do agente).
- `clear_registry()` existe APENAS para testes — nao usar em codigo de producao.
- O metodo `to_schema()` retorna a forma canonica documentada na FASE 02.01.
  Cada provider traduz para seu formato.
- `parse_args` e o ponto unico de validacao — no agent loop sempre passamos pelo
  `execute_tool_call` (que valida) antes de chamar `run`.
- `requires_confirm=True` indica intencao destrutiva. A logica de confirmacao
  vive em `permissions.py` (FASE 07.02), nao aqui.
- Nao confundir `Tool.Input` (nested Pydantic model declarado pelo subclass) com
  outras abstracoes — e a unica forma que o decorator aceita.

---

## Etapas de Implementacao

### Etapa 1: Criar `tools/base.py`

Conteudo conforme acima.

### Etapa 2: Atualizar `tools/__init__.py`

Re-exportar nomes publicos.

### Etapa 3: Criar `tests/test_tools/test_base.py`

```python
"""Tests for Tool ABC, @tool decorator, registry, and execute_tool_call."""
import pytest
from pydantic import BaseModel

from vulpcode.providers import ToolCall
from vulpcode.tools import (
    Tool,
    ToolResult,
    clear_registry,
    execute_tool_call,
    get_tool,
    list_tools,
    tool,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_decorator_registers_tool():
    @tool(name="Echo", description="echoes back")
    class EchoTool(Tool):
        class Input(BaseModel):
            text: str

        async def run(self, args):
            return ToolResult(output=args.text)

    assert get_tool("Echo") is EchoTool
    assert EchoTool._tool_name == "Echo"
    assert EchoTool._requires_confirm is False


def test_decorator_requires_input_class():
    with pytest.raises(TypeError):
        @tool(name="NoInput", description="bad")
        class NoInput(Tool):
            async def run(self, args):
                return ToolResult()


def test_decorator_rejects_non_tool():
    with pytest.raises(TypeError):
        @tool(name="X", description="x")
        class NotATool:  # type: ignore[misc]
            class Input(BaseModel):
                x: int


def test_duplicate_name_rejected():
    @tool(name="Dup", description="d")
    class A(Tool):
        class Input(BaseModel):
            pass
        async def run(self, args):
            return ToolResult()

    with pytest.raises(ValueError):
        @tool(name="Dup", description="d2")
        class B(Tool):
            class Input(BaseModel):
                pass
            async def run(self, args):
                return ToolResult()


def test_to_schema():
    @tool(name="Add", description="adds")
    class AddTool(Tool):
        class Input(BaseModel):
            a: int
            b: int

        async def run(self, args):
            return ToolResult(output=str(args.a + args.b))

    schema = AddTool.to_schema()
    assert schema["name"] == "Add"
    assert schema["description"] == "adds"
    assert schema["input_schema"]["properties"]["a"]["type"] == "integer"


@pytest.mark.asyncio
async def test_execute_tool_call_happy_path():
    @tool(name="Hello", description="h")
    class Hello(Tool):
        class Input(BaseModel):
            who: str

        async def run(self, args):
            return ToolResult(output=f"hi {args.who}")

    tc = ToolCall(id="1", name="Hello", arguments={"who": "world"})
    res = await execute_tool_call(tc)
    assert res.output == "hi world"
    assert not res.is_error


@pytest.mark.asyncio
async def test_execute_tool_call_invalid_args():
    @tool(name="Need", description="n")
    class Need(Tool):
        class Input(BaseModel):
            x: int

        async def run(self, args):
            return ToolResult(output=str(args.x))

    tc = ToolCall(id="1", name="Need", arguments={})
    res = await execute_tool_call(tc)
    assert res.is_error
    assert "Invalid arguments" in (res.error or "")


@pytest.mark.asyncio
async def test_execute_tool_call_unknown():
    tc = ToolCall(id="1", name="Nope", arguments={})
    with pytest.raises(KeyError):
        await execute_tool_call(tc)
    res = await execute_tool_call(tc, allow_unknown=True)
    assert res.is_error
```

### Etapa 4: Rodar testes

```bash
pytest tests/test_tools/test_base.py -v
```

Todos passam.

---

## Criterios de Aceite

- [x] `src/vulpcode/tools/base.py` criado com `Tool`, `ToolResult`, `@tool`, `TOOL_REGISTRY`
- [x] Decorator valida que classe e subclass de `Tool` e tem `Input` nested model
- [x] Decorator rejeita nomes duplicados com `ValueError`
- [x] `Tool.to_schema()` produz dict com `name`, `description`, `input_schema` (JSON Schema)
- [x] `execute_tool_call(tc)` valida args, executa e retorna `ToolResult`
- [x] `clear_registry()`, `get_tool()`, `list_tools()` exportados e funcionando
- [x] `tools/__init__.py` re-exporta a API publica
- [x] `tests/test_tools/test_base.py` criado com >=8 testes, todos passando

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Registry global poluindo entre testes | Alta | Medio | Fixture autouse com `clear_registry` |
| JSON schema incompativel com providers | Baixa | Alto | Validar nas tarefas dos providers |
| Pydantic genericos quebram type checker | Baixa | Baixo | Usar `BaseModel` explicito em assinaturas |

---

**End of Specification**
