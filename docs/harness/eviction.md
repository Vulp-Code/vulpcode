# Eviction & Overflow Clip

Use quando o histórico de mensagens crescer além do que o provider suporta ou
quando quiser manter o custo de tokens sob controle em sessões longas. O
middleware remove pares antigos `assistant + tool_result` quando o limite
configurado é atingido, preservando mensagens de sistema e as últimas N
mensagens recentes.

## Configuração

```toml
[middleware.eviction]
enabled = true
max_messages = 200          # evicta quando len(messages) > max_messages
max_tokens = 80000          # evicta quando tokens estimados > max_tokens (opcional)
keep_recent = 20            # nunca evicta as últimas N mensagens
keep_first_system = true    # preserva mensagens role="system" iniciais
drop_strategy = "oldest_pair"  # única estratégia implementada
```

## Overflow clip

```toml
[middleware.overflow_clip]
enabled = true
max_tool_output_chars = 8000  # trunca outputs maiores que isso
head_chars = 4000
tail_chars = 1000
```

## Exemplo de uso direto

```python
from vulpcode.harness.eviction import EvictionConfig, evict_messages
from vulpcode.harness.hooks import HookBus

bus = HookBus()
cfg = EvictionConfig(enabled=True, max_messages=100, keep_recent=20)

def eviction_hook(state, **_):
    evict_messages(state, cfg)

bus.register("before_iteration", eviction_hook)
```

## Troubleshooting

**Mensagens não são evictadas:** `evict_messages` só remove mensagens do tipo
`assistant` que têm `tool_calls` (pares assistant+tool_result). Histórico de
user+assistant simples (sem tool calls) não é removido por design.

**Eviction infinita:** se nenhum par evictável existir dentro da janela
protegida, o loop para automaticamente para evitar loop infinito.
