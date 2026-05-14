# Tarefa 14.01 - Build e Smoke Tests

**Status**: PENDENTE
**Fase**: 14 - Build + Smoke
**Dependencias**: TODAS as fases anteriores
**Bloqueia**: Nada (ultima tarefa)

---

## Objetivo

Verificar que o projeto:
1. Compila um wheel + sdist sem erros via `python -m build`.
2. `pip install -e .` instala em ambiente limpo.
3. Smoke tests end-to-end basicos passam (`vulp --help`, `vulp providers`,
   round-trip de turno com mock provider).
4. CLI responde aos modos `--print`, `--auto`, `--plan`.
5. Estrutura final de arquivos esta correta.

---

## Descricao Tecnica

### Etapas de smoke test

1. **Limpeza**:
   ```bash
   rm -rf /home/guhaase/projetos/vulpcode/dist /home/guhaase/projetos/vulpcode/build
   find /home/guhaase/projetos/vulpcode -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
   find /home/guhaase/projetos/vulpcode -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
   ```

2. **Build via hatchling**:
   ```bash
   cd /home/guhaase/projetos/vulpcode
   python -m pip install --upgrade build
   python -m build
   ls dist/
   # Esperado: vulpcode-0.1.0.tar.gz e vulpcode-0.1.0-py3-none-any.whl
   ```

3. **Instalar editable + verificar**:
   ```bash
   pip install -e .
   vulp --help
   vulp --version
   vulp providers
   ```

4. **Smoke test do REPL com mock**:

   Criar `tests/test_smoke_cli.py` que:
   - Configura um provider stub via env var `VULPCODE_PROVIDER=stub` (precisa
     adicionar `stub` ao registry de providers em modo "test only").
   - **OU** invoca `start_repl(...)` diretamente em uma fixture com Provider
     mockado e verifica que processa um prompt.

   Aproach mais simples: integration test em Python:

   ```python
   import asyncio
   import pytest
   from typing import AsyncIterator

   from vulpcode.agent import Agent
   from vulpcode.providers.base import Provider, StreamChunk
   from vulpcode.permissions import Mode, PermissionManager
   from vulpcode.tools import list_tools


   class StubProvider(Provider):
       name = "stub"
       async def stream(self, messages, tools, model, system=None, **kwargs) -> AsyncIterator[StreamChunk]:
           yield StreamChunk(type="text", delta="hello from stub")
           yield StreamChunk(type="stop")
       def supports_tools(self): return True
       def supports_vision(self): return False


   @pytest.mark.asyncio
   async def test_full_agent_turn():
       provider = StubProvider()
       tools = [cls() for cls in list_tools()]
       perms = PermissionManager(config={}, mode=Mode.AUTO)
       agent = Agent(provider=provider, tools=tools, permissions=perms)
       text = await agent.run_to_completion("hello")
       assert "hello from stub" in text
   ```

5. **Verificar smoke do --print**:

   Necessita um provider real ou um stub. O CLI ainda nao tem injecao de
   stub. Marcar este como skipped a menos que ANTHROPIC_API_KEY esteja
   definido no ambiente:

   ```python
   import os
   import subprocess
   import pytest


   @pytest.mark.skipif(
       not os.environ.get("ANTHROPIC_API_KEY"),
       reason="No API key for live smoke test",
   )
   def test_print_mode_with_real_api():
       result = subprocess.run(
           ["vulp", "--print", "say hi in one word"],
           capture_output=True, text=True, timeout=60,
       )
       assert result.returncode == 0
       assert len(result.stdout.strip()) > 0
   ```

### Verificacao final do projeto

Estrutura esperada (`tree -L 3 src tests --noreport` ou similar):

```
src/vulpcode/
    __init__.py
    __main__.py
    cli.py
    app.py
    agent.py
    config.py
    session.py
    permissions.py
    providers/
        __init__.py
        base.py
        anthropic.py
        openai.py
        gemini.py
        ollama.py
        registry.py
    tools/
        __init__.py
        base.py
        _bash_registry.py
        bash.py
        bash_background.py
        read.py
        write.py
        edit.py
        glob.py
        grep.py
        web.py
        todo.py
        task.py
        notebook.py
    mcp/
        __init__.py
        client.py
        loader.py
    ui/
        __init__.py
        theme.py
        render.py
        streaming.py
        repl.py
    commands/
        __init__.py
        _base.py
        tools.py
        cost.py
        compact.py
        provider_model.py
        session_cmds.py
        mcp_cmd.py

tests/
    __init__.py
    conftest.py
    test_agent.py
    test_agent_extended.py
    test_cli_skeleton.py
    test_cli_extended.py
    test_commands.py
    test_config.py
    test_mcp_client.py
    test_mcp_loader.py
    test_permissions.py
    test_session.py
    test_ui_render.py
    test_ui_streaming.py
    test_smoke_cli.py
    test_providers/
    test_tools/
    fixtures/
```

### Documento minimo

Criar `CHANGELOG.md` na raiz com:

```markdown
# Changelog

## [0.1.0] - 2026-05-06

Initial release. Multi-provider terminal coding agent with:
- Providers: Anthropic, OpenAI (+ DeepSeek/Groq/OpenRouter), Gemini, Ollama
- Tools: Read, Write, Edit, MultiEdit, Bash (+ background), Glob, Grep, WebFetch, WebSearch, Task, TodoWrite, NotebookEdit
- MCP client
- Slash commands: /help /clear /exit /tools /cost /compact /provider /model /save /load /mcp
- Session persistence with --resume
- Permission modes: default, auto, safe, plan
```

(README e LICENSE ja existem desde FASE 01.02.)

---

## INSTRUCAO CRITICA

- Nao tentar fazer publish no PyPI nesta fase — isso e v1.0 release, fora do
  escopo do desenvolvimento.
- Smoke test com API key real e opcional — `pytest.skipif` quando ausente.
- Wheel deve ser `py3-none-any` (puro Python, sem extensoes).
- Antes de finalizar, garantir que `pytest` global passa SEM `--capture=no` e
  sem `-x`, com a suite inteira. Se alguma flake aparecer, identificar e fixar.
- `python -m build` requer que `build` esteja instalado (`pip install build`).
  Tambem requer `hatchling` (ja em build-system requires no pyproject).

---

## Etapas de Implementacao

### Etapa 1: Limpar artifacts e construir

```bash
cd /home/guhaase/projetos/vulpcode
rm -rf dist build
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
python -m pip install --upgrade build
python -m build
ls dist/
```

Esperado: dois arquivos em `dist/`.

### Etapa 2: Instalar e verificar

```bash
pip install -e .
vulp --help
vulp --version
vulp providers
```

Tudo deve funcionar.

### Etapa 3: Criar `tests/test_smoke_cli.py`

Conforme descrito.

### Etapa 4: Criar `CHANGELOG.md`

### Etapa 5: Rodar suite final

```bash
pytest tests/ -v
```

Todos os testes passam.

### Etapa 6: Smoke real (opcional)

Se houver `ANTHROPIC_API_KEY` no ambiente:

```bash
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY vulp --print "say hi"
```

Deve retornar resposta do modelo.

### Etapa 7: Verificacao da estrutura

```bash
find src tests -type f -name "*.py" | wc -l
# Deve listar todos os arquivos do projeto
```

---

## Criterios de Aceite

- [x] `python -m build` produz `dist/vulpcode-0.1.0.tar.gz` e `dist/vulpcode-0.1.0-py3-none-any.whl`
- [x] `pip install -e .` instala sem erro
- [x] `vulp --help` exibe ajuda completa
- [x] `vulp --version` imprime `vulpcode 0.1.0`
- [x] `vulp providers` lista todos os providers
- [x] `tests/test_smoke_cli.py` cria StubProvider e completa um turno end-to-end
- [x] `pytest tests/` passa toda a suite
- [x] Cobertura global >= 70% (verificar com `pytest --cov=src/vulpcode`)
- [x] `CHANGELOG.md` criado na raiz
- [x] Estrutura de diretorios corresponde ao layout esperado (verificar via `find` e comparar com a lista da spec)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Build falha por hatch version path errado | Baixa | Alto | Verificar `__version__` em `__init__.py` |
| Wheel inclui arquivos errados | Baixa | Medio | `[tool.hatch.build.targets.wheel] packages` correto |
| Smoke real falha por rate limit | Media | Baixo | Skipif quando sem chave |
| Imports residuais quebram build | Baixa | Alto | Rodar `pytest tests/` antes do build |

---

**End of Specification**
