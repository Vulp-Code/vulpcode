# Tarefa 01.01 - Estrutura do Pacote

**Status**: PENDENTE
**Fase**: 01 - Bootstrap
**Dependencias**: Nenhuma
**Bloqueia**: Todas as demais tarefas

---

## Objetivo

Criar o esqueleto de diretorios e arquivos `__init__.py` do pacote `vulpcode` em
`src/vulpcode/`, seguindo o layout `src/`-style. Isto e a base sobre a qual todo o
codigo sera adicionado nas tarefas seguintes.

---

## Descricao Tecnica

**Layout final esperado** (apos esta tarefa):

```
/home/guhaase/projetos/vulpcode/
├── src/
│   └── vulpcode/
│       ├── __init__.py              # versao + exports
│       ├── __main__.py              # python -m vulpcode
│       ├── cli.py                   # placeholder (FASE 01.03)
│       ├── app.py                   # placeholder
│       ├── agent.py                 # placeholder
│       ├── config.py                # placeholder
│       ├── session.py               # placeholder
│       ├── permissions.py           # placeholder
│       │
│       ├── providers/
│       │   └── __init__.py
│       ├── tools/
│       │   └── __init__.py
│       ├── mcp/
│       │   └── __init__.py
│       ├── ui/
│       │   └── __init__.py
│       └── commands/
│           └── __init__.py
│
└── tests/
    ├── __init__.py
    ├── test_providers/
    │   └── __init__.py
    ├── test_tools/
    │   └── __init__.py
    └── fixtures/
        └── __init__.py
```

**Conteudo de `src/vulpcode/__init__.py`**:

```python
"""Vulpcode - terminal coding agent, multi-provider."""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

**Conteudo de `src/vulpcode/__main__.py`**:

```python
"""Entry point for ``python -m vulpcode``."""
from vulpcode.cli import main

if __name__ == "__main__":
    main()
```

**Placeholders** dos modulos (`cli.py`, `app.py`, `agent.py`, `config.py`, `session.py`,
`permissions.py`): cada um deve conter apenas um docstring de uma linha. Por exemplo:

```python
"""Typer CLI entry point."""
```

Estes serao preenchidos nas fases subsequentes.

---

## INSTRUCAO CRITICA

- Use o layout `src/` (pacote dentro de `src/vulpcode/`), nao `vulpcode/` na raiz.
  Isto isola o pacote durante desenvolvimento e evita import acidental do
  diretorio de trabalho.
- Cada `__init__.py` de subpacote pode ser vazio ou conter apenas o docstring.
- Nao criar `pyproject.toml` ainda — isso e a tarefa 01.02.
- Nao implementar codigo real nos placeholders — apenas docstring.

---

## Etapas de Implementacao

### Etapa 1: Criar diretorios

```bash
mkdir -p /home/guhaase/projetos/vulpcode/src/vulpcode/{providers,tools,mcp,ui,commands}
mkdir -p /home/guhaase/projetos/vulpcode/tests/{test_providers,test_tools,fixtures}
```

### Etapa 2: Criar `__init__.py` do pacote raiz

`src/vulpcode/__init__.py` com `__version__ = "0.1.0"` e `__all__ = ["__version__"]`.

### Etapa 3: Criar `__main__.py`

Importa `main` de `vulpcode.cli` (que ainda nao existe — sera placeholder).

### Etapa 4: Criar placeholders dos modulos top-level

Cada arquivo com apenas docstring:
- `cli.py` -> "Typer CLI entry point."
- `app.py` -> "Vulpcode REPL orchestration."
- `agent.py` -> "Agent loop: LLM <-> tools."
- `config.py` -> "Configuration loader (~/.vulpcode/config.toml)."
- `session.py` -> "Session history persistence."
- `permissions.py` -> "Tool execution permission system."

Tambem adicionar em `cli.py` apenas:
```python
"""Typer CLI entry point."""

def main() -> None:
    """Placeholder — implemented in tarefa 01.03."""
    raise NotImplementedError("CLI not yet implemented")
```

para que `__main__.py` consiga importar sem erro.

### Etapa 5: Criar `__init__.py` vazios dos subpacotes

`providers/__init__.py`, `tools/__init__.py`, `mcp/__init__.py`, `ui/__init__.py`,
`commands/__init__.py`: docstring de uma linha.

### Etapa 6: Criar estrutura de tests

`tests/__init__.py`, `tests/test_providers/__init__.py`, `tests/test_tools/__init__.py`,
`tests/fixtures/__init__.py`: vazios ou com docstring.

### Etapa 7: Verificacao

```bash
cd /home/guhaase/projetos/vulpcode
find src tests -type f -name "*.py" | sort
```

Deve listar todos os arquivos criados. Estrutura final verificada com `tree src tests`
(se disponivel).

---

## Criterios de Aceite

- [x] Diretorio `src/vulpcode/` existe com `__init__.py` contendo `__version__ = "0.1.0"`
- [x] `src/vulpcode/__main__.py` importa `main` de `vulpcode.cli`
- [x] Subpacotes `providers/`, `tools/`, `mcp/`, `ui/`, `commands/` existem com `__init__.py`
- [x] Placeholders `app.py`, `agent.py`, `config.py`, `session.py`, `permissions.py` criados
- [x] `cli.py` tem stub `main()` que levanta `NotImplementedError`
- [x] Diretorio `tests/` com subdiretorios `test_providers/`, `test_tools/`, `fixtures/`
- [x] Todos os arquivos sao Python valido (`python -c "import ast; ast.parse(open(p).read())"` passa)

---

## Riscos Tecnicos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Import circular nos placeholders | Baixa | Baixo | Placeholders nao se importam entre si |
| Layout `src/` confunde editores | Baixa | Baixo | Padrao moderno, suportado por todas IDEs |

---

**End of Specification**
