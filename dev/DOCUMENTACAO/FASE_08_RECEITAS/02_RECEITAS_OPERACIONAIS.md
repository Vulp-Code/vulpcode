# Tarefa 08.02 - Receitas Operacionais

**Status**: PENDENTE
**Fase**: 08 - Receitas
**Dependencias**: 08.01
**Bloqueia**: nada

---

## Objetivo

Criar 3 receitas operacionais: debugar bug, gerar documentacao, trabalhar
offline com Ollama.

---

## Arquivos a criar

- `docs/recipes/debug-bug.md`
- `docs/recipes/generate-docs.md`
- `docs/recipes/offline-with-ollama.md`

---

## Conteudo de `debug-bug.md`

Cenario: voce tem um bug e quer ajuda investigando.

Passos:
1. Reproduzir:
   ```
   > rode o comando que reproduz o bug. capture o stack trace.
   ```
2. Investigar:
   ```
   > leia o arquivo na linha do erro. me diga o que pode ter causado.
   ```
3. Hipoteses:
   ```
   > liste 3 hipoteses para o bug, ordenadas pela mais provavel.
   ```
4. Validar:
   ```
   > teste a primeira hipotese: <descrever teste>. se confirma, propoe correcao.
   ```
5. Aplicar:
   ```
   > aplique a correcao. rode os testes para confirmar.
   ```
6. Regressao:
   ```
   > escreva um teste que falharia com o codigo antigo e passa com o novo.
   ```

Anti-patterns:
- Pedir "conserte tudo" sem reproduzir o bug
- Aceitar primeira correcao sem validar

---

## Conteudo de `generate-docs.md`

Cenario: voce quer gerar/atualizar docs para um modulo.

Passos:
1. Inventario:
   ```
   > liste as funcoes/classes publicas em src/foo/ que tem docstring vazia ou ausente
   ```
2. Padronizar:
   ```
   > adicione docstrings no formato Google em todas as funcoes/classes listadas. mantenha consistencia.
   ```
3. Verificar:
   ```
   > rode mkdocs build --strict (se mkdocstrings esta configurado) e me diga se aparece algum warning
   ```

Variantes:
- Gerar README de zero: `> escreva um README.md baseado em src/foo/__init__.py`
- Migrar de NumPy style para Google style: `> converta as docstrings de src/foo.py de NumPy para Google style`

---

## Conteudo de `offline-with-ollama.md`

Cenario: voce esta sem internet ou nao quer enviar codigo para fora da maquina.

Passos:
1. Instalar Ollama:
   ```bash
   curl https://ollama.com/install.sh | sh
   ```
2. Baixar um modelo (qwen2.5-coder e bom em codigo):
   ```bash
   ollama pull qwen2.5-coder:7b
   # ou para maquinas com mais RAM:
   ollama pull qwen2.5-coder:14b
   ```
3. Configurar vulpcode:
   ```toml
   # ~/.vulpcode/config.toml
   default_provider = "ollama"
   default_model = "qwen2.5-coder:7b"
   ```
4. Testar:
   ```bash
   vulp --auto "explique git rebase em 1 linha"
   ```

Modelos recomendados (off-line) por tarefa:

| Tarefa             | Modelo                      | RAM minima |
|--------------------|-----------------------------|------------|
| Codigo geral       | `qwen2.5-coder:7b`          | 8 GB       |
| Codigo grande      | `qwen2.5-coder:14b`         | 16 GB      |
| Chat geral         | `llama3.1:8b`               | 8 GB       |
| Vision (imagens)   | `llava:7b`                  | 8 GB       |

Limitacoes:
- Tool calling depende do modelo. `qwen2.5-coder` suporta. Modelos mais antigos
  podem falhar.
- Streaming funciona, mas mais lento que API paga.
- Modelos < 7B sao limitados para tarefas agenticas.

Notas de performance:
- WSL: garanta que GPU passthrough esta funcionando (`nvidia-smi` na WSL)
- macOS: Ollama usa Metal automaticamente
- Linux: instale `nvidia-cuda-toolkit` se tiver GPU NVIDIA

Variantes:
- Servidor Ollama remoto: `[providers.ollama] base_url = "http://server:11434"`
- vLLM em vez de Ollama: troca pelo provider `vllm`

---

## Atualizar `mkdocs.yml`

As entradas ja foram adicionadas em 08.01. Nao mexer.

---

## INSTRUCAO CRITICA

- Tabela de modelos: marcar RAM realista. Ollama com `qwen2.5-coder:7b`
  consome ~6GB.
- Mencionar que `--auto` recomendado para receitas (evita interrupcoes).

---

## Etapas de Implementacao

### Etapa 1: Criar 3 arquivos de receita
### Etapa 2: `mkdocs build`

---

## Criterios de Aceite

- [x] `docs/recipes/debug-bug.md` com 6 passos
- [x] `docs/recipes/generate-docs.md` com inventario + padronizar + verificar
- [x] `docs/recipes/offline-with-ollama.md` com setup completo + tabela de modelos
- [x] `mkdocs build` continua passando

---

**End of Specification**
