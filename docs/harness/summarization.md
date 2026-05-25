# Auto-Summarization

Use quando a sessão durar muitas horas e o histórico acumular tokens demais. A
sumarização preserva mensagens de sistema e as últimas `keep_recent_messages`
mensagens, e substitui tudo no meio por uma mensagem de resumo gerada pelo
próprio provider — sem perder o contexto mais recente.

## Configuração

```toml
[middleware.summarization]
enabled = true
trigger_at_tokens = 50000      # dispara quando tokens estimados > isso
keep_recent_messages = 10      # preserva as últimas N mensagens
target_tokens = 20000          # tokens alvo após resumo
cooldown_iterations = 5        # iterações de espera entre sumarizações
```

## Como funciona

1. `before_iteration`: conta tokens estimados das mensagens atuais.
2. Se `trigger_at_tokens` for atingido e o cooldown tiver passado, faz uma
   chamada ao provider com as mensagens a resumir.
3. O texto gerado substitui o meio do histórico como `role="system"`.
4. `state.metadata["last_summarization_iteration"]` é atualizado.

## Exemplo de uso direto

```python
from vulpcode.harness.summarization import SummarizationConfig, SummarizationHook
from vulpcode.harness.hooks import HookBus

bus = HookBus()
cfg = SummarizationConfig(enabled=True, trigger_at_tokens=50000, keep_recent_messages=10)
hook = SummarizationHook(cfg, provider=provider, model="")
bus.register("before_iteration", hook)
```

## Troubleshooting

**Summarization não dispara:** verifique `trigger_at_tokens` e se o cooldown
(`cooldown_iterations`) não está impedindo. A contagem de tokens é estimada
(~4 chars/token) e pode diferir do real.

**Loops de sumarização:** ocorre se o resumo gerado ainda for maior que
`target_tokens`. Aumente `target_tokens` ou reduza `keep_recent_messages`.
