# Tarefa 02.02 - Primeira Configuracao

**Status**: PENDENTE
**Fase**: 02 - Getting Started
**Dependencias**: 02.01
**Bloqueia**: 02.03

---

## Objetivo

Criar `getting-started/first-config.md` mostrando como configurar o vulpcode
pela primeira vez: hierarquia de config (env vars > config.toml local >
config.toml global > defaults), exemplos para cada provider basico.

---

## Arquivos a criar

- `docs/getting-started/first-config.md`

---

## Source de verdade

- `src/vulpcode/config.py` — DEFAULTS, ENV_MAP, hierarquia
- `src/vulpcode/providers/registry.py` — nomes dos providers
- `src/vulpcode/permissions.py` — Mode (default, auto, safe, plan)

---

## Estrutura sugerida

### 1. Onde fica a configuracao

- `~/.vulpcode/config.toml` (global, por usuario)
- `<projeto>/.vulpcode/config.toml` (por projeto, sobrescreve global)
- Variaveis de ambiente
- Flags de CLI (mais alta prioridade)

Diagrama (texto) da hierarquia.

### 2. Criar config.toml minimo

Mostrar 4 abas (`=== "Aba"`):

- **Anthropic**:
  ```toml
  default_provider = "anthropic"
  default_model = "claude-sonnet-4-6"

  [providers.anthropic]
  api_key = "sk-ant-..."
  ```
- **OpenAI**:
  ```toml
  default_provider = "openai"
  default_model = "gpt-4o-mini"

  [providers.openai]
  api_key = "sk-..."
  ```
- **Ollama (offline)**:
  ```toml
  default_provider = "ollama"
  default_model = "qwen2.5-coder:7b"

  [providers.ollama]
  base_url = "http://localhost:11434"
  ```
- **Endpoint corporativo**:
  ```toml
  default_provider = "internal-llm"
  default_model = "internal-llm"

  [providers.internal-llm]
  base_url = "http://internal.example.com/v1/chat"
  user_uuid = "00000000-0000-0000-0000-000000000000"
  ```

### 3. Variaveis de ambiente reconhecidas

Tabela com a lista de `ENV_MAP` em `config.py`. Exemplo:

| Env var                  | Mapeia para                              |
|--------------------------|------------------------------------------|
| `VULPCODE_PROVIDER`      | `default_provider`                       |
| `VULPCODE_MODEL`         | `default_model`                          |
| `ANTHROPIC_API_KEY`      | `providers.anthropic.api_key`            |
| `OPENAI_API_KEY`         | `providers.openai.api_key`               |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | `providers.gemini.api_key`    |
| `DEEPSEEK_API_KEY`       | `providers.deepseek.api_key`             |
| `GROQ_API_KEY`           | `providers.groq.api_key`                 |
| `OPENROUTER_API_KEY`     | `providers.openrouter.api_key`           |
| `INTERNAL_LLM_ENDPOINT`  | `providers.internal-llm.base_url`        |
| `INTERNAL_LLM_USER_UUID` | `providers.internal-llm.user_uuid`       |

### 4. Subcomando `vulp config`

Explicar que `vulp config` abre o `~/.vulpcode/config.toml` no `$EDITOR`,
criando o arquivo se nao existir.

### 5. Verificacao

```bash
vulp providers   # confirma quais sao reconhecidos
vulp models      # lista modelos do provider configurado (alguns)
```

### 6. Boas praticas de seguranca

- **Nao commite** `~/.vulpcode/config.toml` no git (esta no `.gitignore` se a
  pasta `.vulpcode` esta listada).
- **Para CI**: use env vars, nao arquivos.
- **Para compartilhar config sem secrets**: copie config.toml mas remova api_keys
  e use placeholders.

---

## Atualizar `mkdocs.yml`

A entrada `Primeira configuracao` ja foi adicionada em 02.01. Nada a fazer aqui.

---

## INSTRUCAO CRITICA

- Verificar a lista de env vars contra `ENV_MAP` em `src/vulpcode/config.py`
  ANTES de finalizar — pode ter mudado.
- O nome do provider para Gemini reconhece TANTO `GEMINI_API_KEY` quanto
  `GOOGLE_API_KEY` — deixar claro que ambos funcionam.
- Internal-llm: enfatizar que **NUNCA** se hardcoda URL/UUID em codigo aberto;
  sempre via env ou config local.

---

## Etapas de Implementacao

### Etapa 1: Ler `src/vulpcode/config.py` e confirmar ENV_MAP atual
### Etapa 2: Criar `getting-started/first-config.md`
### Etapa 3: Validar que comandos exemplo funcionam (`vulp providers`)
### Etapa 4: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/getting-started/first-config.md` criado
- [x] Hierarquia de config explicada (DEFAULTS < global < projeto < env < CLI)
- [x] 4 abas de exemplo config.toml (Anthropic, OpenAI, Ollama, internal-llm)
- [x] Tabela completa de env vars reconhecidas (10 entradas, batendo com `ENV_MAP`)
- [x] Subcomando `vulp config` documentado
- [x] Secao de boas praticas de seguranca
- [x] `mkdocs build` continua passando

---

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| ENV_MAP foi alterado | Reler o arquivo antes de fechar |
| Usuario compartilha config com chave | Aviso explicito de seguranca |

---

**End of Specification**
