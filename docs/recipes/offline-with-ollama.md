# Trabalhar offline com Ollama

> **Cenario**: voce esta sem internet, ou o codigo nao pode sair da
> maquina (NDA, dados sensiveis, ambiente air-gapped). Quer rodar o
> Vulpcode 100% local com [Ollama](https://ollama.com/).
> **Tempo estimado**: 10-20 minutos para setup inicial (depende do
> download do modelo); zero overhead nas execucoes seguintes.
> **Provider recomendado**: Ollama com `qwen2.5-coder:7b` para coding
> agent, `llama3.1:8b` para chat geral.

## Contexto

Modelos locais nao tem custo por token, nao saem da maquina e funcionam
sem internet — mas sao mais lentos, tem janela de contexto menor, e nem
todos suportam tool calling. Esse fluxo te leva de "Ollama nao instalado"
ate "Vulpcode rodando offline" sem surpresas.

> **Modo recomendado:** `--auto` para trabalho offline. Modelos locais
> ja sao mais lentos no primeiro token; cada confirmacao manual
> multiplica a latencia percebida. Veja
> [Modos de permissao](../user-guide/permission-modes.md).

## Passos

### 1. Instalar Ollama

```bash
# Linux / macOS
curl https://ollama.com/install.sh | sh

# Windows: baixe o instalador em https://ollama.com/download
```

Apos instalar, o servidor sobe em `http://localhost:11434`. Confirme:

```bash
curl http://localhost:11434/api/tags
# {"models":[]}  ← ainda sem modelos
```

### 2. Baixar um modelo capaz de tool calling

`qwen2.5-coder` e o que melhor equilibra qualidade de codigo e custo de
RAM em hardware modesto:

```bash
ollama pull qwen2.5-coder:7b

# Ou para maquinas com mais RAM/GPU:
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5-coder:32b
```

> O download da uma media de 4-20 GB dependendo do modelo. Faca antes
> de ficar offline.

### 3. Configurar o Vulpcode

Edite `~/.vulpcode/config.toml` (cria a pasta se nao existir):

```toml
default_provider = "ollama"
default_model = "qwen2.5-coder:7b"

[providers.ollama]
# base_url default = "http://localhost:11434"
# Se Ollama roda em outra maquina/porta, descomente:
# base_url = "http://server:11434"
timeout = 300.0  # modelos locais sao lentos no primeiro carregamento
```

> Veja [`config.toml`](../configuration/config-toml.md) para outras
> chaves. Variaveis de ambiente equivalentes em
> [Variaveis de ambiente](../configuration/env-vars.md).

### 4. Testar com `--auto`

```bash
vulp --auto "explique git rebase em 1 linha"
```

Primeiro request demora alguns segundos enquanto o modelo carrega na VRAM.
Os seguintes sao mais rapidos. Se vir `connection refused`, o servidor
Ollama caiu — rode `ollama serve` num terminal separado.

### 5. Confirmar tool calling

```bash
vulp --auto "use Read para abrir README.md e me devolva o titulo"
```

Se o modelo respondeu o titulo correto, tool calling esta funcionando.
Se respondeu "nao tenho acesso aos arquivos" ou texto sem chamar tool,
o modelo nao foi treinado para tools — troque para outro (veja tabela
abaixo) ou rode `ollama list` para ver alternativas baixadas.

---

## Modelos recomendados (off-line) por tarefa

A coluna **RAM minima** e o que efetivamente carrega na memoria
(modelo + KV cache + overhead). Em CPU pura, espere ~2× mais lento que
em GPU.

| Tarefa             | Modelo                      | RAM minima | Tool calling | Notas                              |
|--------------------|-----------------------------|------------|--------------|------------------------------------|
| Codigo geral       | `qwen2.5-coder:7b`          | ~6 GB      | OK           | Recomendado para o caminho feliz.  |
| Codigo grande      | `qwen2.5-coder:14b`         | ~12 GB     | OK           | Melhor raciocinio, mais memoria.   |
| Codigo top-tier    | `qwen2.5-coder:32b`         | ~24 GB     | OK           | Requer GPU robusta (24+ GB VRAM).  |
| Chat geral         | `llama3.1:8b`               | ~6 GB      | OK           | Conversa, doc, planejamento.       |
| Chat top-tier      | `llama3.1:70b`              | ~48 GB     | OK           | Hardware potente (datacenter).     |
| Vision (imagens)   | `llava:7b`                  | ~6 GB      | parcial      | Tool calling depende do tag.       |
| Alternativa leve   | `mistral:latest`            | ~5 GB      | OK           | Bom fallback se RAM apertada.      |

> A tabela canonica de modelos com tool-calling esta em
> [Provider Ollama](../providers/ollama.md#modelos-disponiveis). Esta
> aqui e o subset relevante para uso como agente offline.

---

## Limitacoes

- **Tool calling depende do modelo.** O provider envia tools no formato
  OpenAI-compatible, mas modelos sem fine-tuning de tool-calling
  (como `phi3` ou `gemma2` antigos) **ignoram** as tools silenciosamente.
  `qwen2.5-coder` e `llama3.1` sao seguros.
- **Streaming funciona, mas mais lento que API paga.** A latencia do
  primeiro token depende do load do modelo na VRAM (segundos ate
  dezenas de segundos no primeiro request). Por isso o `timeout=300.0`
  do provider — nao reduza demais.
- **Modelos < 7B sao limitados para tarefas agenticas.** `qwen2.5-coder:1.5b`
  ate roda, mas falha em prompts multi-step. Para agente, comece em 7B.
- **Janela de contexto menor.** Maioria dos modelos locais tem 8k-32k
  tokens — bem abaixo do que Claude/GPT aceitam. Em sessoes longas,
  use `/compact` mais cedo. Veja
  [Slash commands](../user-guide/slash-commands.md).
- **Argumentos podem chegar como string.** Cobertura no provider
  (`ollama.py:127`) ja decodifica, mas se o modelo gerar JSON
  invalido o tool call e descartado. Re-tente ou troque de modelo.

---

## Notas de performance

- **WSL**: garanta que o GPU passthrough esta funcionando antes de
  baixar modelos grandes:

    ```bash
    nvidia-smi  # dentro da WSL — precisa listar a GPU
    ```

    Se nao listar, instale os drivers WSL-CUDA da NVIDIA no Windows
    host. Sem GPU, fica em CPU — funciona, mas ~5x mais lento.

- **macOS**: Ollama usa **Metal** automaticamente em Apple Silicon
  (M1/M2/M3/M4). Nada para configurar. Em Intel Macs, fica em CPU.

- **Linux**: instale `nvidia-cuda-toolkit` se tiver GPU NVIDIA. Para
  AMD, a versao mais recente do Ollama ja suporta ROCm — confira a
  [documentacao oficial](https://github.com/ollama/ollama/blob/main/docs/gpu.md).

- **Primeiro request e lento sempre.** Ollama carrega o modelo "lazy"
  na primeira chamada. Para warmup, rode um request descartavel antes
  do trabalho real.

---

## Variantes

### Servidor Ollama remoto (compartilhado em rede interna)

Se uma maquina mais potente roda Ollama e voce quer usar do laptop:

```toml
[providers.ollama]
base_url = "http://server:11434"
timeout = 300.0
```

> **Atencao:** Ollama **nao tem autenticacao**. Em rede compartilhada,
> exponha apenas via firewall/VPN. Veja
> [Provider Ollama / Notas](../providers/ollama.md#notas-e-limitacoes).

### vLLM em vez de Ollama

[vLLM](https://docs.vllm.ai/) tem throughput maior em GPU, mas e mais
complexo de operar. O Vulpcode tem provider dedicado:

```toml
default_provider = "vllm"
default_model = "Qwen/Qwen2.5-Coder-7B-Instruct"

[providers.vllm]
base_url = "http://localhost:8000/v1"  # default
```

Sobe o servidor vLLM separado (`vllm serve <model>`). Vale se voce
ja tem um servidor compartilhado em produção.

### LM Studio em vez de Ollama

`lmstudio` tambem e suportado nativamente:

```toml
default_provider = "lmstudio"

[providers.lmstudio]
base_url = "http://localhost:1234/v1"  # default
```

Use a UI do LM Studio para baixar e ativar modelos. Util em maquinas
sem terminal-friendly setup.

### Hibrido: Ollama para classificacao, Claude para tarefas longas

Quando offline nao e absoluto, alterna providers em runtime:

```bash
vulp --auto
> /provider ollama
> /model qwen2.5-coder:7b
> resuma esse arquivo: <arquivo.py>
> /provider anthropic
> /model claude-sonnet-4-5
> agora refatore mantendo a API publica
```

Veja [Trocar provider em runtime](../providers/switching-at-runtime.md).

---

## Anti-patterns / armadilhas

- **Esperar paridade com Claude/GPT.** `qwen2.5-coder:7b` e bom em
  Python idiomatico, mas tropeca em raciocinio multi-step longo. Para
  refactor grande ou debug complexo, considere voltar para a nuvem.
- **Rodar 32B+ sem GPU adequada.** Em CPU, um 32B leva minutos por
  resposta. Se sua maquina nao tem 24+ GB de VRAM, fique em 7B-14B.
- **Esquecer `ollama serve` rodando.** Se vir `connection refused`,
  o servidor caiu (e Ollama nao auto-restarta). Em macOS, o app GUI
  mantem; em Linux/WSL, voce pode precisar de um systemd service.
- **`base_url` apontando para `127.0.0.1` num container.** Dentro de
  Docker/devcontainer, `localhost` e o **container**, nao o host. Use
  `http://host.docker.internal:11434` ou o IP do host.
- **Modelos quantizados q2/q3 para coding.** Qualidade despenca rapido
  abaixo de q4. Use o tag default (`qwen2.5-coder:7b`, que e q4_K_M)
  e so desca se RAM for problema absoluto.
- **Confiar em `WebSearch` quando a internet caiu.** A tool
  `WebSearch` precisa de backend online (Tavily). Vai falhar com
  `WebSearch backend unavailable`. Em offline puro,
  [`WebFetch`](../tools/web.md) **tambem** falha — desligue o uso de
  qualquer tool de rede no prompt.

---

## Veja tambem

- [Provider Ollama](../providers/ollama.md) — referencia completa do
  provider, incluindo NDJSON, list_models, e mapeamento de tool ids.
- [Trocar provider em runtime](../providers/switching-at-runtime.md) —
  alternar Ollama ↔ Anthropic na mesma sessao.
- [Configuracao / `config.toml`](../configuration/config-toml.md) —
  todas as chaves de `[providers.ollama]`.
- [Configuracao / Variaveis de ambiente](../configuration/env-vars.md) —
  `VULPCODE_PROVIDER`, `VULPCODE_MODEL` para overrides rapidos.
- [Modos de permissao](../user-guide/permission-modes.md) — por que
  `--auto` casa bem com offline.
- [Slash commands](../user-guide/slash-commands.md) — `/compact`
  importante em sessao offline (janela menor).
- [Documentacao oficial Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md).
