# Primeira configuracao

Esta pagina mostra como configurar o Vulpcode pela primeira vez: onde os
arquivos vivem, qual e a hierarquia de precedencia, exemplos minimos para
cada provider e boas praticas para nao vazar segredos.

> **Pressuposto**: voce ja tem o `vulp` instalado. Se nao, volte para
> [Instalacao](installation.md).

---

## 1. Onde fica a configuracao

O Vulpcode procura configuracao em **quatro fontes**, da mais fraca para a
mais forte:

| Fonte | Caminho | Escopo |
|-------|---------|--------|
| Defaults internos | `vulpcode.config.DEFAULTS` | Todos |
| Config global | `~/.vulpcode/config.toml` | Por usuario |
| Config de projeto | `<projeto>/.vulpcode/config.toml` | Pasta atual ou qualquer ancestral |
| Variaveis de ambiente | `ENV_MAP` em `config.py` | Processo atual |
| Flags de CLI | `vulp --provider ... --model ...` | Invocacao atual |

A descoberta de config de projeto sobe a arvore de diretorios a partir do
`cwd`: a primeira pasta com `.vulpcode/config.toml` vence.

### Diagrama de precedencia

```text
DEFAULTS                              (mais fraco)
    |
    v  merge profundo
~/.vulpcode/config.toml               (global)
    |
    v  merge profundo
<projeto>/.vulpcode/config.toml       (projeto, sobrescreve global)
    |
    v  set por chave
variaveis de ambiente                 (ENV_MAP)
    |
    v  merge profundo
flags de CLI                          (mais forte)
```

Cada camada faz **merge profundo** sobre a anterior — chaves nao mencionadas
sao preservadas; listas sao substituidas, nao concatenadas.

---

## 2. Criar `config.toml` minimo

Crie `~/.vulpcode/config.toml` com **um** dos exemplos abaixo. Use
`vulp config` (descrito mais adiante) se preferir abrir no `$EDITOR`.

=== "Anthropic"

    ```toml
    default_provider = "anthropic"
    default_model = "claude-sonnet-4-6"

    [providers.anthropic]
    api_key = "sk-ant-..."
    ```

=== "OpenAI"

    ```toml
    default_provider = "openai"
    default_model = "gpt-4o-mini"

    [providers.openai]
    api_key = "sk-..."
    ```

=== "Ollama (offline)"

    ```toml
    default_provider = "ollama"
    default_model = "qwen2.5-coder:7b"

    [providers.ollama]
    base_url = "http://localhost:11434"
    ```

    Nao precisa de `api_key`: o Ollama nao usa autenticacao por padrao.
    Garanta que `ollama serve` esta rodando e que o modelo foi puxado
    com `ollama pull qwen2.5-coder:7b`.

=== "Endpoint corporativo"

    ```toml
    default_provider = "internal-llm"
    default_model = "internal-llm"

    [providers.internal-llm]
    base_url = "http://internal.example.com/v1/chat"
    user_uuid = "00000000-0000-0000-0000-000000000000"
    ```

    !!! danger "Nunca hardcode URL ou UUID em codigo aberto"
        O endpoint `internal-llm` e tipicamente um proxy interno de uma
        empresa. **Nao commite** `base_url` nem `user_uuid` em repositorios
        publicos. Prefira variaveis de ambiente
        (`INTERNAL_LLM_ENDPOINT`, `INTERNAL_LLM_USER_UUID`) ou um
        `.vulpcode/config.toml` local que esteja no `.gitignore`.

> **Outros providers**: os mesmos blocos `[providers.<nome>]` valem para
> `gemini`, `deepseek`, `groq`, `openrouter`, `lmstudio` e `vllm`. Veja a
> lista completa com `vulp providers`.

---

## 3. Variaveis de ambiente reconhecidas

Toda variavel listada abaixo, se presente, sobrescreve o valor do
`config.toml`. As chaves seguem `ENV_MAP` em `src/vulpcode/config.py`.

| Env var                              | Mapeia para                              |
|--------------------------------------|------------------------------------------|
| `VULPCODE_PROVIDER`                  | `default_provider`                       |
| `VULPCODE_MODEL`                     | `default_model`                          |
| `ANTHROPIC_API_KEY`                  | `providers.anthropic.api_key`            |
| `OPENAI_API_KEY`                     | `providers.openai.api_key`               |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY`  | `providers.gemini.api_key`               |
| `DEEPSEEK_API_KEY`                   | `providers.deepseek.api_key`             |
| `GROQ_API_KEY`                       | `providers.groq.api_key`                 |
| `OPENROUTER_API_KEY`                 | `providers.openrouter.api_key`           |
| `INTERNAL_LLM_ENDPOINT`              | `providers.internal-llm.base_url`        |
| `INTERNAL_LLM_USER_UUID`             | `providers.internal-llm.user_uuid`       |

> **Gemini**: `GEMINI_API_KEY` e `GOOGLE_API_KEY` sao **equivalentes** —
> ambos preenchem `providers.gemini.api_key`. Se as duas estiverem
> definidas, a ultima processada vence; na pratica, exporte apenas uma.

Exemplo de uso pontual:

```bash
VULPCODE_PROVIDER=ollama VULPCODE_MODEL=qwen2.5-coder:7b vulp "explique esse repo"
```

---

## 4. Subcomando `vulp config`

```bash
vulp config
```

O `vulp config`:

1. Garante que `~/.vulpcode/` existe (cria se necessario).
2. Cria `~/.vulpcode/config.toml` com um cabecalho minimo se ainda nao
   existir.
3. Abre o arquivo no editor definido por `$EDITOR`, depois `$VISUAL`,
   caindo para `vi` se nenhum estiver setado.

```bash
EDITOR=nvim vulp config   # forca um editor especifico nesta invocacao
```

Para criar uma config **por projeto**, basta rodar manualmente:

```bash
mkdir -p .vulpcode && $EDITOR .vulpcode/config.toml
```

---

## 5. Verificacao

Confirme que o Vulpcode reconhece o que voce configurou:

```bash
vulp providers   # tabela com providers conhecidos e backend
vulp models      # lista modelos do provider configurado
```

A saida de `vulp providers` lista cada provider com seu backend
(dedicado ou OpenAI-compativel). Se voce ve o nome esperado e o
`default_provider` correto, a config foi carregada.

---

## 6. Boas praticas de seguranca

!!! warning "Nunca commite chaves no git"
    O `~/.vulpcode/config.toml` mora no seu home — fora de qualquer repo —
    o que ja e seguro. **Cuidado** com o `<projeto>/.vulpcode/config.toml`:
    adicione `.vulpcode/` ao `.gitignore` do projeto antes de salvar
    qualquer chave nele.

- **Em CI**, use **variaveis de ambiente** (`ANTHROPIC_API_KEY`, etc.)
  injetadas via secrets do runner. Nao versione `config.toml` com chaves.
- **Para compartilhar config sem segredos**, copie o `config.toml` mas
  troque `api_key = "sk-..."` por placeholders (`api_key = "<set via env>"`)
  e remova `user_uuid` do bloco `internal-llm`.
- **Internal-llm**: trate `base_url` e `user_uuid` como segredos. Mesmo que
  o UUID nao seja uma chave, ele identifica o usuario perante o proxy
  corporativo. Use sempre env vars ou config local fora do git.
- **Rotacione chaves** se voce suspeitar que vazaram (commit acidental,
  pasted em log, etc.).

---

## Proximos passos

- [Conceitos principais](core-concepts.md): provider, modelo, modos de
  permissao, sessao.
- [Quickstart](quickstart.md): tutorial guiado usando a config que voce
  acabou de criar.
