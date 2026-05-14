# Tarefa 06.02 - Permissoes Avancadas

**Status**: PENDENTE
**Fase**: 06 - Configuracao
**Dependencias**: 06.01
**Bloqueia**: nada

---

## Objetivo

Criar `configuration/permissions.md` cobrindo: customizacao de permissoes,
prompter customizado (programatico), allowlist persistente, integracao com
PermissionManager.

---

## Arquivos a criar

- `docs/configuration/permissions.md`

---

## Source de verdade

- `src/vulpcode/permissions.py` — `PermissionManager`, `stdin_prompter`, `Mode`
- `src/vulpcode/ui/streaming.py` — wrapper que pausa o spinner durante prompt
- `src/vulpcode/app.py` — `_make_permissions`

---

## Estrutura

### 1. Recap dos modos

(link para [User Guide → Modos de permissao](../user-guide/permission-modes.md))

### 2. Allowlist persistente

```toml
[permissions]
always_allow_tools = ["Read", "Glob", "Grep", "Bash"]
```

Comportamento: cada tool listada e tratada como ja-aprovada na sessao. Util
para perfis de seguranca:

- **Dev local**: `["Read", "Write", "Edit", "Bash", "Glob", "Grep"]`
- **Demo / observador**: `[]` (pede tudo)
- **CI**: nao usar; usar `--auto`

### 3. Customizar o prompter (programatico)

Caso de uso: usar a biblioteca como SDK em vez de via REPL.

```python
from vulpcode.permissions import PermissionManager, Mode

async def my_prompter(message: str, ctx: dict) -> str:
    # Custom logic — log to disk, ask via Slack, etc.
    print(f"Permission request: {message} | args: {ctx['arguments']}")
    return "y"  # always approve, or implement real logic

pm = PermissionManager(
    config={},
    mode=Mode.DEFAULT,
    prompter=my_prompter,
)
```

O prompter recebe `(message: str, ctx: dict)` onde `ctx = {"name": str,
"arguments": dict}` e retorna `"y"` / `"a"` / `"n"`.

### 4. Integracao com REPL

O `stream_agent_turn` em `ui/streaming.py` substitui o prompter durante o
turno por um wrapper que **pausa o spinner Rich**, executa o prompter
original (stdin), e religa o spinner. Isso e necessario porque Rich.Live
rouba a stdout enquanto roda.

Se voce esta construindo uma UI custom (nao Rich), considere:
- Implementar um prompter que use `await asyncio.to_thread(input, ...)` ou
  similar
- OU integrar com seu sistema de eventos (Discord bot, web socket, etc.)

### 5. Boas praticas de seguranca

- **Producao**: nunca `Mode.AUTO` com input nao confiavel.
- **Dev**: `always_allow_tools` para tools que voce ja revisou; pede para o
  resto.
- **Hooks**: voce pode interceptar antes do `PermissionManager.check`
  customizando o `Agent` (ver [contributing/](../contributing/index.md)).
- **Logging**: tools chamadas e permission decisions ja sao emitidas como
  eventos (`ToolStartEvent`, `ToolDeniedEvent`); facil hookar com observabilidade.

### 6. Tabelas de referencia

#### Tools com `requires_confirm=True`

(verificar contra source — Bash, Write, Edit, MultiEdit, KillBash, NotebookEdit)

#### Tools com `requires_confirm=False`

(Read, Glob, Grep, BashOutput, WebFetch, WebSearch, Task, TodoWrite)

---

## INSTRUCAO CRITICA

- Confirmar a lista contra `@tool(..., requires_confirm=...)` em cada arquivo
  de tool.
- Para o exemplo de prompter customizado, garantir que a assinatura bate com
  `PrompterFn = Callable[[str, dict], Awaitable[str]]`.

---

## Etapas de Implementacao

### Etapa 1: Ler `permissions.py`, `ui/streaming.py`
### Etapa 2: Criar `configuration/permissions.md`
### Etapa 3: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/configuration/permissions.md` criado
- [x] Recap dos 4 modos
- [x] Secao sobre `always_allow_tools` com perfis de uso
- [x] Exemplo de prompter customizado (codigo Python real)
- [x] Mencao ao spinner-aware wrapper em `streaming.py`
- [x] Boas praticas de seguranca
- [x] Tabelas de tools confirm/no-confirm batem com source
- [x] `mkdocs build` continua passando

---

**End of Specification**
