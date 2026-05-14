# Comece aqui

Bem-vindo a documentacao do **Vulpcode**. Esta secao guia voce do zero ate o
primeiro chat funcional, em qualquer provider.

## Roteiro sugerido

1. [Instalacao](installation.md) — `pip install vulpcode`, virtualenv, extras opcionais.
2. [Quickstart](quickstart.md) — primeiro chat em 5 minutos.
3. [Primeira configuracao](first-config.md) — `~/.vulpcode/config.toml`.
4. [Conceitos principais](core-concepts.md) — agente, tools, permissoes.

## Pre-requisitos

- Python 3.11 ou superior (`python --version`)
- `pip` recente (`pip install --upgrade pip`)
- Linux ou macOS (Windows: WSL recomendado)
- Pelo menos uma chave de API (Anthropic, OpenAI, Gemini, ...) **OU** Ollama
  rodando localmente

## Em qual ordem ler?

Se voce so quer **testar** o Vulpcode rapido, va direto para o
[Quickstart](quickstart.md) — ele assume zero configuracao previa e te poe num
chat funcional em poucos comandos.

Se voce quer **integrar o Vulpcode no seu fluxo** (multiplos providers, MCP,
permissoes, perfis), leia na ordem listada acima — cada pagina pressupoe a
anterior.
