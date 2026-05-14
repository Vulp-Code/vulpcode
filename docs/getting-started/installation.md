# Instalacao

Vulpcode e distribuido no PyPI como um pacote Python puro. Requer **Python 3.11
ou superior** e instala dois console scripts: `vulp` (curto) e `vulpcode`
(longo, equivalente).

## Recomendado: virtualenv

Sempre instale o Vulpcode em um ambiente isolado para nao poluir o Python do
sistema.

=== "Linux / WSL"

    ```bash
    python -m venv ~/.venv/vulpcode
    source ~/.venv/vulpcode/bin/activate
    pip install --upgrade pip
    pip install vulpcode
    ```

=== "macOS"

    ```bash
    python3 -m venv ~/.venv/vulpcode
    source ~/.venv/vulpcode/bin/activate
    pip install --upgrade pip
    pip install vulpcode
    ```

=== "Windows (PowerShell)"

    Sem WSL, o suporte a Windows nativo e best-effort. Prefira WSL.

    ```powershell
    python -m venv $HOME\.venv\vulpcode
    $HOME\.venv\vulpcode\Scripts\Activate.ps1
    pip install --upgrade pip
    pip install vulpcode
    ```

Para ativar o ambiente em sessoes futuras, repita apenas o passo `source ...`
(ou `Activate.ps1`).

## Instalacao basica

Sem virtualenv (nao recomendado para uso diario, mas util em containers
descartaveis):

```bash
pip install --user vulpcode
```

Confira que `~/.local/bin` (Linux) ou o equivalente do seu sistema esta no
`PATH`, senao o comando `vulp` nao sera encontrado.

## Extras opcionais

Vulpcode declara tres grupos de extras em `pyproject.toml`. Instale apenas o
que voce precisa.

| Extra      | O que adiciona                                  | Quando usar                               |
| ---------- | ----------------------------------------------- | ----------------------------------------- |
| `[dev]`    | `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `respx` | Contribuintes rodando a suite de testes |
| `[docs]`   | `mkdocs`, `mkdocs-material`, `mkdocstrings[python]`, `pymdown-extensions` | Quem vai gerar este site localmente |
| `[search]` | `duckduckgo-search`                             | Usar a tool `WebSearch` sem chave Tavily |

Sintaxe:

```bash
pip install "vulpcode[search]"
pip install "vulpcode[dev,docs]"
```

As aspas sao **obrigatorias** em zsh e em alguns shells, porque `[` e `]` sao
caracteres especiais.

## Instalacao a partir do source

Para acompanhar a `main` ou trabalhar em um patch:

```bash
git clone https://github.com/vulpcode/vulpcode.git
cd vulpcode
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev,docs,search]"
```

O modo `-e` (editable) faz com que mudancas em `src/vulpcode/` apareçam
imediatamente no comando `vulp`, sem reinstalar.

## Verificacao

Depois de instalar, valide com dois comandos:

```bash
vulp --version
# vulpcode 0.1.0

vulp providers
```

A saida de `vulp providers` deve listar 10 nomes:

```
                Vulpcode providers
+--------------+---------------------------------+
| name         | backend                         |
+--------------+---------------------------------+
| anthropic    | Anthropic                       |
| deepseek     | OpenAI-compatible (https://...) |
| gemini       | Gemini                          |
| groq         | OpenAI-compatible (https://...) |
| internal-llm | Internal-llm                    |
| lmstudio     | OpenAI-compatible (http://...)  |
| ollama       | Ollama                          |
| openai       | OpenAI-compatible (default)     |
| openrouter   | OpenAI-compatible (https://...) |
| vllm         | OpenAI-compatible (http://...)  |
+--------------+---------------------------------+
```

Se voce ve essa tabela, a instalacao esta correta. O proximo passo e
[configurar uma chave de API e iniciar o primeiro chat](quickstart.md).

## Atualizar

```bash
pip install --upgrade vulpcode
```

## Desinstalar

```bash
pip uninstall vulpcode
```

A configuracao em `~/.vulpcode/` **nao** e removida — apague manualmente se
quiser zerar o estado:

```bash
rm -rf ~/.vulpcode
```

## Resolucao de problemas

- **`vulp: command not found`** — o `bin` do seu virtualenv (ou `~/.local/bin`
  para `--user`) nao esta no `PATH`. Reative o venv ou ajuste o `PATH`.
- **`Python 3.10 nao suportado`** — atualize seu Python. Vulpcode requer 3.11+.
- **Erro de SSL ao instalar** — atualize `pip` (`pip install --upgrade pip`) e
  `certifi`.
