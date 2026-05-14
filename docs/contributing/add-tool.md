# Adicionar uma tool

Este guia mostra como criar uma tool nativa que o LLM pode invocar (ex:
enviar email, rodar query SQL, criar issue no GitHub).

A fonte da verdade e `src/vulpcode/tools/base.py`. Os exemplos foram
conferidos contra esse arquivo. Para um overview do registry e do dispatch,
veja [Tool registry](../architecture/tool-registry.md) e
[API: Tools](../api/tools.md).

## Como uma tool e definida

Toda tool e:

1. Uma subclasse de [`Tool`](../api/tools.md) com um `class Input(BaseModel)`
   aninhado (que define os argumentos e vira o JSON Schema enviado ao LLM).
2. Um metodo `async def run(self, args: BaseModel) -> ToolResult`.
3. Decorada com `@tool(name=..., description=..., requires_confirm=...)`,
   que registra a classe em `TOOL_REGISTRY`.

O agent loop chama `Tool.to_schema()` para construir a lista de tools
enviada a cada provider, recebe `ToolCall` do stream, valida os argumentos
contra `Input` e despacha via `execute_tool_call` (em `tools/base.py`).

## Estrutura minima

Crie `src/vulpcode/tools/sua.py`:

```python
"""Sua tool — descricao curta do arquivo."""
from __future__ import annotations

from pydantic import BaseModel, Field

from vulpcode.tools.base import Tool, ToolResult, tool


@tool(
    name="SuaTool",
    description="Descricao curta — o LLM le isso para decidir quando usar.",
    requires_confirm=False,  # True para acoes destrutivas
)
class SuaTool(Tool):
    """Docstring opcional — explica para o desenvolvedor o que a tool faz."""

    class Input(BaseModel):
        param1: str = Field(description="O que param1 representa.")
        param2: int = Field(default=0, description="Quantidade — default 0.")
        flag: bool = False

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, SuaTool.Input)

        # ... logica ...

        if not args.param1:
            return ToolResult(
                error="param1 nao pode estar vazio",
                is_error=True,
            )

        resultado = f"recebi {args.param1!r} e param2={args.param2}"

        return ToolResult(
            output=resultado,                  # vai de volta ao LLM
            metadata={"k": "v"},               # opcional, fica no log/UI
        )
```

### Registrar

Em `src/vulpcode/tools/__init__.py`, adicione um import (a posicao no fim
do arquivo importa — registros so acontecem na importacao do modulo):

```python
from vulpcode.tools import sua as _sua  # noqa: E402, F401  (registers SuaTool)
```

Pronto. O agent loop ja vai descobrir `SuaTool` na proxima execucao.

## Anatomia do `@tool`

```python
@tool(
    name: str,                  # nome unico no TOOL_REGISTRY (visivel ao LLM)
    description: str,           # texto que o LLM le para escolher a tool
    requires_confirm: bool = False,
)
```

- `name`: tem que ser unico globalmente. Levanta `ValueError` se ja existir
  no `TOOL_REGISTRY`. Convencao: `PascalCase` (`Read`, `Bash`, `WebFetch`).
- `description`: o LLM consome isso. Diga **o que faz**, nao **como faz**.
- `requires_confirm=True` faz o runtime pedir confirmacao do usuario antes
  de cada execucao (em modos de permissao seguros). Use para qualquer acao
  com efeito colateral significativo.

## ToolResult

```python
class ToolResult(BaseModel):
    output: str = ""             # texto enviado de volta ao LLM (sucesso)
    error: str | None = None     # texto da falha
    is_error: bool = False       # True para sinalizar falha
    metadata: dict[str, Any] = {}  # nao vai ao LLM, fica no log/UI
```

Em sucesso, preencha `output`. Em falha, prefira retornar
`ToolResult(error="...", is_error=True)` em vez de `raise`. Erros nao
levantados sao convertidos para `ToolResult(is_error=True)` automaticamente
pelo `execute_tool_call`, mas controlar a mensagem voce mesmo da resultados
mais limpos para o LLM.

## Boas praticas

- **`description` clara e concreta.** O LLM ve isso e usa para decidir
  quando invocar. Mau: "uses async httpx to send a POST request". Bom:
  "Send an email to a recipient".
- **`Input` enxuto.** Minimize argumentos. Use `Field(description="...")`
  em cada campo — o JSON Schema gerado leva isso para o LLM e ajuda a
  acertar a chamada.
- **`requires_confirm=True`** quando a tool: escreve em disco, executa
  shell, faz request externo, deleta dados, modifica estado compartilhado.
- **Output curto.** O LLM paga tokens por palavra do output e ele entra no
  contexto da proxima volta. Truncate resultados longos com sufixo
  `"...[truncated, X more lines]"`.
- **Erros descritivos.** `ToolResult(error="File does not exist: <path>",
  is_error=True)` e melhor que `error="ENOENT"` — o LLM consegue tentar
  outra coisa em vez de travar.
- **Idempotencia quando possivel.** Se o LLM re-invocar a mesma operacao
  por engano, prefira que nao corrompa estado.

## Tests

Em `tests/test_tools/test_sua.py`:

```python
import pytest
import vulpcode.tools  # noqa: F401  (carrega o registry inteiro)
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_sua_happy_path():
    cls = get_tool("SuaTool")
    res = await cls().run(cls.Input(param1="x"))
    assert not res.is_error
    assert "x" in res.output


@pytest.mark.asyncio
async def test_sua_invalid_input():
    cls = get_tool("SuaTool")
    with pytest.raises(Exception):
        cls.Input()  # falta param1 obrigatorio


@pytest.mark.asyncio
async def test_sua_error_case():
    cls = get_tool("SuaTool")
    res = await cls().run(cls.Input(param1=""))
    assert res.is_error
    assert "vazio" in (res.error or "")


def test_sua_registered():
    cls = get_tool("SuaTool")
    assert cls._tool_name == "SuaTool"
    assert cls._tool_description.startswith("Descricao")
    assert cls._requires_confirm is False
```

Rode com `pytest tests/test_tools/test_sua.py -v`.

## Patterns avancados

### Tools com estado entre chamadas

Para uma tool que mantem estado (lista de todos, sessoes de bash em
background, registro de permissoes concedidas), use um dict module-level
como o `_TODO_STORE` em `src/vulpcode/tools/todo.py`:

```python
_SUA_STORE: dict[str, MyState] = {}


@tool(name="SuaTool", description="...")
class SuaTool(Tool):
    class Input(BaseModel):
        session_id: str = "default"

    async def run(self, args):
        state = _SUA_STORE.setdefault(args.session_id, MyState())
        ...
```

Quando o estado e mais complexo (processos vivos, locks, cleanup), extraia
para um modulo separado — `src/vulpcode/tools/_bash_registry.py` faz isso
para o `Bash`. Convencao: nome com `_` no inicio para sinalizar privado.

### Background work

Para tools que dispararam trabalho assincrono (ex: `Bash` com
`run_in_background=True`), use `asyncio.create_task` para spawnar o worker
e devolva imediatamente um id. O usuario consulta o resultado depois com
uma tool separada (ex: `BashOutput`). Veja `src/vulpcode/tools/bash.py`
(funcao `_drain`) e `src/vulpcode/tools/bash_background.py`.

### Permission tracking

Se a tool precisa rastrear "ja perguntei isso?" entre invocacoes, use
`metadata` na `ToolResult` e o callback de permissao do session manager.
Nao reinvente — veja como `Bash` integra com `PermissionManager` antes de
ir por esse caminho.

## Checklist final

- [ ] Tool em `src/vulpcode/tools/<sua>.py` com `@tool(...)` aplicado.
- [ ] `class Input(BaseModel)` com `Field(description=...)` nos campos.
- [ ] Import em `src/vulpcode/tools/__init__.py` para registrar.
- [ ] Tests em `tests/test_tools/test_<sua>.py` cobrindo happy path,
      input invalido, caso de erro, registro.
- [ ] `requires_confirm=True` se for destrutiva.
- [ ] Doc em `docs/tools/<categoria>.md` (ver
      [Tools](../tools/index.md)) — entrada no nome da tool, args,
      output, exemplo.
- [ ] Linha nova na tabela em `docs/tools/index.md`.
- [ ] `pytest tests/` passa.
- [ ] `mkdocs build --strict` passa sem warnings.

Veja tambem: [Adicionar um provider](add-provider.md),
[Convencoes de codigo](code-conventions.md),
[Tool registry](../architecture/tool-registry.md).
