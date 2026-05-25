# Harness

O harness é o sistema de middleware do Vulpcode: um barramento de eventos (`HookBus`) onde componentes registram funções para interceptar, observar ou transformar o que acontece a cada iteração do loop do agente. Use o harness quando quiser controlar comportamento sem modificar o código central — por exemplo: evitar overflow de contexto, bloquear chamadas de ferramentas sensíveis, injetar instruções dinâmicas ou resumir o histórico automaticamente.

## Loop e eventos

```
 ┌────────────────────────────────────────────────────────┐
 │                    Agent loop                          │
 │                                                        │
 │  before_iteration ──► provider.stream()                │
 │                            │                           │
 │                    before_send (injeção de mensagens)  │
 │                            │                           │
 │                       tool_calls?                      │
 │                       /        \                       │
 │          before_tool_call    (blocked/patched)         │
 │                  │                                     │
 │             tool.run()                                 │
 │                  │                                     │
 │          after_tool_call  ──► resultado transformado   │
 │                                                        │
 │  before_compress  (antes de compactar o histórico)     │
 └────────────────────────────────────────────────────────┘
```

| Evento             | Quando dispara                                      |
|--------------------|-----------------------------------------------------|
| `before_iteration` | Início de cada ciclo LLM, antes de enviar mensagens |
| `before_send`      | Antes de montar o payload para o provider           |
| `before_tool_call` | Antes de executar cada tool call                    |
| `after_tool_call`  | Após a execução, com o `ToolResult` disponível      |
| `before_compress`  | Antes de compactar/resumir o histórico manualmente  |

## Componentes de middleware

| Componente       | Evento             | O que faz                                               |
|------------------|--------------------|---------------------------------------------------------|
| Eviction         | `before_iteration` | Remove pares assistant+tool antigos quando limite de mensagens/tokens é atingido |
| Summarization    | `before_iteration` | Resume o meio do histórico com o provider quando tokens ultrapassam o threshold |
| OverflowClip     | `after_tool_call`  | Trunca outputs de tools muito grandes                   |
| ContextHub       | `after_tool_call`  | Descarrega outputs grandes para disco, injeta preview   |
| ToolPatch        | `before_tool_call` | Redact, block ou log de tool calls por regex            |
| SkillRegistry    | `before_send`      | Injeta descritor de skills no system prompt             |
| SkillToolFilter  | `before_tool_call` | Bloqueia tools não listadas na skill ativa              |

## Páginas de referência

- [hooks.md](hooks.md) — API do HookBus, registro de hooks customizados
- [profiles.md](profiles.md) — Perfis nomeados de configuração
- [skills.md](skills.md) — Skills: playbooks injetados sob demanda
- [eviction.md](eviction.md) — Eviction e overflow clip
- [summarization.md](summarization.md) — Auto-summarização de histórico longo
- [context-hub.md](context-hub.md) — Offload de outputs grandes para disco
- [tool-patch.md](tool-patch.md) — Interceptação e redação de tool calls
- [state.md](state.md) — LoopState e reducers
- [vfs.md](vfs.md) — Virtual filesystem (jail/sandbox)
