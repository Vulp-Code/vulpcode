# HookBus

## Quando usar

Use `HookBus` quando quiser adicionar comportamento customizado ao loop do agente sem alterar o código central. Casos típicos: auditar tool calls, bloquear comandos por política, transformar resultados, injetar contexto dinâmico.

## Registrar um hook

```python
from vulpcode.harness import HookBus
from vulpcode.harness.state import LoopState

bus = HookBus()

def my_hook(state: LoopState, **kwargs) -> None:
    print(f"Iteração {state.iteration}, mensagens: {len(state.messages)}")

my_hook.name = "my_hook"
my_hook.reads = ("messages", "iteration")
my_hook.writes = ()

bus.register("before_iteration", my_hook)
```

Hooks são chamados na **ordem de registro**. Exceções individuais são capturadas e logadas — um hook com erro não aborta o loop.

## Estrutura interna: `_hooks`

```python
bus._hooks == {
    "before_iteration": [...],
    "before_send":      [...],
    "before_tool_call": [...],
    "after_tool_call":  [...],
    "before_compress":  [...],
}
```

Cada valor é uma lista de callables. Registrar o mesmo evento várias vezes empilha os hooks.

## Protocolo de retorno de `before_tool_call`

| Valor retornado | Efeito                                                        |
|-----------------|---------------------------------------------------------------|
| `None`          | No-op — tool call prossegue normalmente                       |
| `False`         | Bloqueia a tool call; modelo recebe mensagem de erro          |
| `ToolCall`      | Substitui o tool call original (patch de argumentos)         |
| `ToolResult`    | Resultado pré-computado; tool não chega a ser executada       |

Para bloquear com mensagem customizada, grave em `state.metadata["last_block_message"]` antes de retornar `False`.

## Protocolo de retorno de `after_tool_call`

| Valor retornado | Efeito                                                   |
|-----------------|----------------------------------------------------------|
| `None`          | No-op — resultado original é mantido                     |
| `ToolResult`    | Substitui o resultado entregue ao modelo                 |

O hook recebe `call` e `result` como kwargs: `hook(state, call=tc, result=result)`.

## Hooks assíncronos

O loop do agente suporta hooks `async`. Basta definir `async def` — o loop faz `await`:

```python
async def async_hook(state: LoopState, **kwargs) -> None:
    await asyncio.sleep(0)  # pode usar await normalmente
    ...

bus.register("before_iteration", async_hook)
```

## Inspecionar hooks registrados

```python
from vulpcode.harness import list_middleware

print(list_middleware(bus))
# Registered middleware (by event):
# before_iteration:
#   - eviction  reads=(messages)  writes=(messages)
```

## Troubleshooting

**Hook não está sendo chamado**
Verifique se `bus.register` foi chamado com o nome de evento correto. Eventos válidos: `before_iteration`, `before_send`, `before_tool_call`, `after_tool_call`, `before_compress`. Qualquer outro nome levanta `ValueError` imediatamente.

**Hook levantou uma exceção e foi silenciado**
Veja os logs em `vulpcode.harness.hooks` (nível `ERROR`). O loop continua mesmo quando um hook falha.

**`before_tool_call` não está bloqueando**
Certifique-se de que o `hook_bus` foi passado ao construtor do `Agent`. Se `agent.hook_bus is None`, nenhum evento é emitido.
