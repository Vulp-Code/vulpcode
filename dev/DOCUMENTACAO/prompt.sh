#!/bin/bash

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Script para executar TAREFAS do Plano de Documentacao do Vulpcode
# Objetivo: Construir docs/ MkDocs Material completo, em 13 fases
# Execucao automatizada via Claude CLI
# COM LOGGING COMPLETO para acompanhamento em tempo real
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# --- CONFIGURACOES ---
TARGET_TIME="00:01"
MAX_ITERATIONS=50

# --- DIRETORIO BASE ---
DOC_DIR="/home/guhaase/projetos/vulpcode/dev/DOCUMENTACAO"
PROJECT_ROOT="/home/guhaase/projetos/vulpcode"

# --- DIRETORIO DE LOG ---
LOG_DIR="${DOC_DIR}/LOG"
mkdir -p "$LOG_DIR"

# Log principal com timestamp no nome
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
MAIN_LOG="${LOG_DIR}/vulpcode_doc_${TIMESTAMP}.log"
LATEST_LOG="${LOG_DIR}/latest.log"

# Criar link simbolico para o log mais recente
ln -sf "$MAIN_LOG" "$LATEST_LOG"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ARQUIVOS DE TAREFAS (ordem topologica respeitando dependencias)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TASK_FILES=(
    # FASE 01 - Bootstrap MkDocs
    "${DOC_DIR}/FASE_01_BOOTSTRAP_MKDOCS/01_MKDOCS_SETUP.md"
    "${DOC_DIR}/FASE_01_BOOTSTRAP_MKDOCS/02_LOGO_E_ASSETS.md"
    "${DOC_DIR}/FASE_01_BOOTSTRAP_MKDOCS/03_INDEX_LANDING.md"

    # FASE 02 - Getting Started
    "${DOC_DIR}/FASE_02_GETTING_STARTED/01_INSTALACAO_E_QUICKSTART.md"
    "${DOC_DIR}/FASE_02_GETTING_STARTED/02_PRIMEIRA_CONFIGURACAO.md"
    "${DOC_DIR}/FASE_02_GETTING_STARTED/03_CONCEITOS_PRINCIPAIS.md"

    # FASE 03 - User Guide do REPL
    "${DOC_DIR}/FASE_03_USER_GUIDE_REPL/01_USANDO_REPL_E_SLASH.md"
    "${DOC_DIR}/FASE_03_USER_GUIDE_REPL/02_MODOS_PERMISSAO.md"
    "${DOC_DIR}/FASE_03_USER_GUIDE_REPL/03_SESSOES_E_HISTORICO.md"

    # FASE 04 - Providers
    "${DOC_DIR}/FASE_04_PROVIDERS/01_PROVIDERS_OVERVIEW.md"
    "${DOC_DIR}/FASE_04_PROVIDERS/02_PROVIDERS_DEDICADOS.md"
    "${DOC_DIR}/FASE_04_PROVIDERS/03_PROVIDERS_OPENAI_COMPAT.md"
    "${DOC_DIR}/FASE_04_PROVIDERS/04_INTERNAL_LLM.md"

    # FASE 05 - Tools
    "${DOC_DIR}/FASE_05_TOOLS/01_TOOLS_OVERVIEW.md"
    "${DOC_DIR}/FASE_05_TOOLS/02_TOOLS_FILESYSTEM_SHELL_BUSCA.md"
    "${DOC_DIR}/FASE_05_TOOLS/03_TOOLS_AGENTE_E_WEB.md"

    # FASE 06 - Configuracao
    "${DOC_DIR}/FASE_06_CONFIGURACAO/01_CONFIG_TOML_E_ENV.md"
    "${DOC_DIR}/FASE_06_CONFIGURACAO/02_PERMISSIONS_AVANCADO.md"

    # FASE 07 - MCP
    "${DOC_DIR}/FASE_07_MCP/01_MCP_GUIDE.md"

    # FASE 08 - Receitas
    "${DOC_DIR}/FASE_08_RECEITAS/01_RECEITAS_DESENVOLVIMENTO.md"
    "${DOC_DIR}/FASE_08_RECEITAS/02_RECEITAS_OPERACIONAIS.md"

    # FASE 09 - API Reference (mkdocstrings)
    "${DOC_DIR}/FASE_09_API_REFERENCE/01_API_PROVIDERS_E_TOOLS.md"
    "${DOC_DIR}/FASE_09_API_REFERENCE/02_API_AGENT_E_PERMISSIONS.md"
    "${DOC_DIR}/FASE_09_API_REFERENCE/03_API_CONFIG_SESSION_MCP.md"

    # FASE 10 - Arquitetura
    "${DOC_DIR}/FASE_10_ARQUITETURA/01_INTERNALS_AGENT_E_STREAMING.md"
    "${DOC_DIR}/FASE_10_ARQUITETURA/02_INTERNALS_PROVIDERS_E_TOOLS.md"

    # FASE 11 - Contributing
    "${DOC_DIR}/FASE_11_CONTRIBUTING/01_SETUP_DEV_E_TESTES.md"
    "${DOC_DIR}/FASE_11_CONTRIBUTING/02_ADICIONAR_PROVIDER_E_TOOL.md"

    # FASE 12 - FAQ
    "${DOC_DIR}/FASE_12_FAQ/01_FAQ_E_TROUBLESHOOTING.md"

    # FASE 13 - Build Final
    "${DOC_DIR}/FASE_13_BUILD_FINAL/01_VERIFICAR_LINKS_E_BUILD.md"
    "${DOC_DIR}/FASE_13_BUILD_FINAL/02_DEPLOY_GITHUB_PAGES.md"
)

# Cores para output no terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FUNCOES DE LOG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$msg" | tee -a "$MAIN_LOG"
}

log_file() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$MAIN_LOG"
}

log_separator() {
    local sep="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$sep" | tee -a "$MAIN_LOG"
}

update_status() {
    local status_file="${LOG_DIR}/status.txt"
    cat > "$status_file" <<EOF
=== STATUS DA DOCUMENTACAO - VULPCODE ===
Atualizado em: $(date '+%Y-%m-%d %H:%M:%S')
Tarefa atual:  $1
Arquivo:       $2
Iteracao:      $3
Pendentes:     $4
Completos:     $5
Estado:        $6
Log completo:  $MAIN_LOG
===========================
EOF
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AGENDAMENTO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
log "Verificando horario de inicio programado para: ${TARGET_TIME}..."

CURRENT_EPOCH=$(date +%s)
TARGET_EPOCH=$(date -d "$TARGET_TIME" +%s)

if [ "$TARGET_EPOCH" -lt "$CURRENT_EPOCH" ]; then
    TARGET_EPOCH=$(date -d "tomorrow $TARGET_TIME" +%s)
fi

SLEEP_SECONDS=$((TARGET_EPOCH - CURRENT_EPOCH))

if [ "$SLEEP_SECONDS" -gt 0 ]; then
    HOURS=$((SLEEP_SECONDS / 3600))
    MINS=$(((SLEEP_SECONDS % 3600) / 60))
    log "Entrando em modo sleep. O script iniciara em ${HOURS}h ${MINS}m."
    echo -e "${GREEN}Pressione ENTER para iniciar imediatamente!${NC}"
    echo -e "${BLUE}Ou pressione Ctrl+C para cancelar o agendamento.${NC}"

    ELAPSED=0
    while [ $ELAPSED -lt $SLEEP_SECONDS ]; do
        read -t 1 -n 1 && break
        ELAPSED=$((ELAPSED + 1))
    done
fi

log "Horario atingido! Iniciando rotinas..."

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AUXILIARES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

count_pending_checkboxes() {
    local file="$1"
    local count=$(grep -c "^- \[ \]" "$file" 2>/dev/null || true)
    echo "${count:-0}"
}

count_completed_checkboxes() {
    local file="$1"
    local count=$(grep -c "^- \[x\]" "$file" 2>/dev/null || true)
    echo "${count:-0}"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GERADOR DE PROMPT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

build_prompt() {
    local task_file="$1"
    local iteration="$2"
    local task_relpath="${task_file#${DOC_DIR}/}"

    cat <<PROMPT_EOF
You are writing user-facing **MkDocs documentation** for **Vulpcode**, a Python
CLI coding agent (multi-provider, agentic) that already exists in
\`${PROJECT_ROOT}/src/vulpcode/\`. The library is feature-complete; your job
is to document it accurately and beautifully.

## Project Context

- **Project root**: \`${PROJECT_ROOT}/\`
- **Source code (the source of truth)**: \`${PROJECT_ROOT}/src/vulpcode/\`
- **Tests (also informative)**: \`${PROJECT_ROOT}/tests/\`
- **CHANGELOG**: \`${PROJECT_ROOT}/CHANGELOG.md\`
- **Pyproject (deps and metadata)**: \`${PROJECT_ROOT}/pyproject.toml\`
- **Documentation root (the docs site)**: \`${PROJECT_ROOT}/docs/\`
- **mkdocs config**: \`${PROJECT_ROOT}/mkdocs.yml\`
- **Plan file you are working on**: \`${task_file}\`

## Site stack

- **MkDocs** + **Material for MkDocs** + **mkdocstrings[python]** for API reference.
- Material features in use: navigation tabs/sections, dark+light theme toggle,
  code copy, content tabs, search.
- Code blocks use language hints (\`\`\`python, \`\`\`bash, \`\`\`toml, ...).
- Internal links use relative .md paths (e.g. \`[providers](../providers/anthropic.md)\`).
- Pages are written in **Portuguese** (consistent with the project's language)
  EXCEPT mkdocs.yml which stays in English.

## Conventions

- **Source of truth = code**. Read the source files referenced in the task spec
  before writing. Do NOT invent flags, env vars, or class names.
- **Cross-link** related pages liberally. The doc is a graph, not a list.
- **Examples are concrete**. Every page should have at least one runnable
  example (CLI command or Python snippet).
- **Concise prose**. Walls of text are anti-pattern. Prefer tables and code.
- **No emojis** unless the user explicitly approves them in the task.
- **Absolute file paths** when referring to files in shell commands.
- For files with secrets in examples (API keys, UUIDs), use placeholders like
  \`sk-ant-...\` or \`00000000-0000-0000-0000-000000000000\`. NEVER paste real
  credentials.

## Your Task

1. Read the task specification below carefully.
2. Read the SOURCE files it references (e.g. \`src/vulpcode/providers/anthropic.py\`)
   so the doc is accurate.
3. Create the \`.md\` files exactly where the spec says, with the structure described.
4. Update \`mkdocs.yml\` nav if a new page needs to appear (the spec will say so).
5. **CRITICAL**: After completing each acceptance criterion, mark its checkbox:
   change \`- [ ]\` to \`- [x]\` in: \`${task_file}\`
6. Skip items already marked \`[x]\`.
7. Continue until ALL checkboxes in this task file are \`[x]\`.

## Important Notes

- Use absolute paths when creating files.
- Create any missing parent directories.
- Do NOT delete pages from previous tasks.
- After making nav changes, run \`mkdocs build --strict\` (when mkdocs is installed)
  and fix any warning before marking the task complete.
- This is iteration #${iteration} for this task. Focus on uncompleted items.

## Task Specification: ${task_relpath}

---
$(cat "$task_file")
---

REMEMBER: Mark each checkbox (\`- [ ]\` -> \`- [x]\`) in \`${task_file}\` as you complete each criterion.
PROMPT_EOF
}

show_progress() {
    local pending=$1
    local completed=$2
    local task_name=$3
    local total=$((pending + completed))
    local percentage=0
    if [ $total -gt 0 ]; then
        percentage=$((completed * 100 / total))
    fi

    log_separator
    log "PROGRESSO ${task_name}"
    log "  Completos:  ${completed}"
    log "  Pendentes:  ${pending}"
    log "  Total:      ${total}"
    log "  Progresso:  ${percentage}%"
    log_separator
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VERIFICACAO DE PRE-REQUISITOS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

log "============================================"
log "LOG DE EXECUCAO INICIADO"
log "Modulo: VULPCODE - Documentacao MkDocs"
log "Objetivo: docs/ completo (~13 fases)"
log "Arquivo de log: $MAIN_LOG"
log "Para acompanhar:"
log "  tail -f $LATEST_LOG"
log "Status rapido:"
log "  cat ${LOG_DIR}/status.txt"
log "============================================"

if ! command -v claude &> /dev/null; then
    log "ERRO: Claude CLI nao encontrado. Instale com: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

log "Verificando arquivos de tarefa..."
for TASK_FILE in "${TASK_FILES[@]}"; do
    if [ ! -f "$TASK_FILE" ]; then
        log "ERRO: Arquivo $TASK_FILE nao encontrado!"
        exit 1
    fi
    log_file "  OK: ${TASK_FILE#${DOC_DIR}/}"
done

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INICIO DA EXECUCAO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOTAL_TASKS=${#TASK_FILES[@]}
EXEC_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log "Iniciando execucao automatica de ${TOTAL_TASKS} tarefas de documentacao"
log "Inicio: ${EXEC_START_TIME}"

for TASK_INDEX in "${!TASK_FILES[@]}"; do
    TASK_FILE="${TASK_FILES[$TASK_INDEX]}"
    TASK_NUM=$((TASK_INDEX + 1))
    TASK_NAME="TAREFA ${TASK_NUM}/${TOTAL_TASKS}"
    TASK_RELPATH="${TASK_FILE#${DOC_DIR}/}"
    TASK_BASENAME=$(basename "$TASK_FILE" .md)

    log ""
    log "======================================================"
    log "INICIANDO ${TASK_NAME} - ${TASK_RELPATH}"
    log "Arquivo: ${TASK_FILE}"
    log "======================================================"

    TASK_LOG="${LOG_DIR}/vulpcode_doc_step${TASK_NUM}_${TASK_BASENAME}_${TIMESTAMP}.log"
    log "Log desta tarefa: ${TASK_LOG}"

    TASK_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
    ITERATION=0

    while [ $ITERATION -lt $MAX_ITERATIONS ]; do
        ITERATION=$((ITERATION + 1))
        PENDING=$(count_pending_checkboxes "$TASK_FILE")
        COMPLETED=$(count_completed_checkboxes "$TASK_FILE")

        show_progress "$PENDING" "$COMPLETED" "$TASK_NAME"
        update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$PENDING" "$COMPLETED" "EXECUTANDO"

        if [ "$PENDING" -eq 0 ]; then
            TASK_END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
            log "SUCESSO! ${TASK_NAME} concluida!"
            log "  Inicio: ${TASK_START_TIME}"
            log "  Fim:    ${TASK_END_TIME}"
            update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "0" "$COMPLETED" "CONCLUIDA"
            break
        fi

        CLAUDE_START=$(date '+%Y-%m-%d %H:%M:%S')
        CLAUDE_START_EPOCH=$(date +%s)
        log "[CLAUDE] Iniciando chamada #${ITERATION} - ${TASK_NAME} (pendentes: ${PENDING})"

        CLAUDE_RAW="${LOG_DIR}/claude_raw_step${TASK_NUM}_iter${ITERATION}.jsonl"
        CLAUDE_READABLE="${LOG_DIR}/claude_readable_step${TASK_NUM}_iter${ITERATION}.log"
        > "$CLAUDE_RAW"
        > "$CLAUDE_READABLE"

        ln -sf "$CLAUDE_RAW" "${LOG_DIR}/claude_current_raw.jsonl"
        ln -sf "$CLAUDE_READABLE" "${LOG_DIR}/claude_current.log"

        update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$PENDING" "$COMPLETED" \
            "CLAUDE EXECUTANDO (inicio: ${CLAUDE_START}) -- tail -f ${LOG_DIR}/claude_current.log"

        log "[CLAUDE] Modo: prompt completo - iteracao ${ITERATION} (stream-json)"
        build_prompt "$TASK_FILE" "$ITERATION" | claude -p --dangerously-skip-permissions --verbose --output-format stream-json > "$CLAUDE_RAW" 2>&1 &
        CLAUDE_PID=$!

        (
            tail -f "$CLAUDE_RAW" --pid=$CLAUDE_PID 2>/dev/null | while IFS= read -r line; do
                TYPE=$(echo "$line" | grep -oP '"type"\s*:\s*"\K[^"]+' | head -1)

                case "$TYPE" in
                    assistant)
                        TEXT=$(echo "$line" | grep -oP '"content"\s*:\s*"\K[^"]*' | head -1)
                        if [ -n "$TEXT" ]; then
                            echo "[$(date '+%H:%M:%S')] [TEXTO] ${TEXT:0:300}" >> "$CLAUDE_READABLE"
                        fi
                        ;;
                    content_block_start)
                        TOOL=$(echo "$line" | grep -oP '"name"\s*:\s*"\K[^"]+' | head -1)
                        if [ -n "$TOOL" ]; then
                            echo "[$(date '+%H:%M:%S')] [TOOL START] $TOOL" >> "$CLAUDE_READABLE"
                        fi
                        ;;
                    content_block_delta)
                        TEXT=$(echo "$line" | grep -oP '"text"\s*:\s*"\K[^"]*' | head -1)
                        if [ -n "$TEXT" ] && [ ${#TEXT} -gt 2 ]; then
                            echo "[$(date '+%H:%M:%S')] [DELTA] ${TEXT:0:200}" >> "$CLAUDE_READABLE"
                        fi
                        ;;
                    result)
                        echo "[$(date '+%H:%M:%S')] [RESULTADO FINAL]" >> "$CLAUDE_READABLE"
                        ;;
                esac
            done
        ) &
        PARSER_PID=$!

        LAST_RAW_SIZE=0
        while kill -0 $CLAUDE_PID 2>/dev/null; do
            RAW_SIZE=$(wc -c < "$CLAUDE_RAW" 2>/dev/null || echo 0)
            RAW_LINES=$(wc -l < "$CLAUDE_RAW" 2>/dev/null || echo 0)
            NOW_EPOCH=$(date +%s)
            ELAPSED_SECS=$((NOW_EPOCH - CLAUDE_START_EPOCH))
            ELAPSED_MIN=$((ELAPSED_SECS / 60))
            ELAPSED_SEC=$((ELAPSED_SECS % 60))

            LIVE_PENDING=$(count_pending_checkboxes "$TASK_FILE")
            LIVE_COMPLETED=$(count_completed_checkboxes "$TASK_FILE")
            LIVE_DONE=$((LIVE_COMPLETED - COMPLETED))

            if [ "$RAW_SIZE" -gt "$LAST_RAW_SIZE" ]; then
                ACTIVITY="ativo"
            else
                ACTIVITY="aguardando API"
            fi
            LAST_RAW_SIZE=$RAW_SIZE

            update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$LIVE_PENDING" "$LIVE_COMPLETED" \
                "CLAUDE | ${ELAPSED_MIN}m${ELAPSED_SEC}s | ${RAW_LINES} eventos | ${ACTIVITY} | +${LIVE_DONE} checkboxes"

            log_file "[MONITOR] ${TASK_NAME} iter#${ITERATION} | ${ELAPSED_MIN}m${ELAPSED_SEC}s | ${RAW_LINES} eventos | ${RAW_SIZE} bytes | ${ACTIVITY} | ${LIVE_COMPLETED}/${LIVE_PENDING}"

            sleep 15
        done

        wait $CLAUDE_PID
        CLAUDE_EXIT_CODE=$?

        sleep 2
        kill $PARSER_PID 2>/dev/null
        wait $PARSER_PID 2>/dev/null

        CLAUDE_END=$(date '+%Y-%m-%d %H:%M:%S')
        FINAL_RAW_LINES=$(wc -l < "$CLAUDE_RAW" 2>/dev/null || echo 0)
        FINAL_RAW_SIZE=$(wc -c < "$CLAUDE_RAW" 2>/dev/null || echo 0)
        log "[CLAUDE] Fim: ${CLAUDE_END} (exit: ${CLAUDE_EXIT_CODE}, ${FINAL_RAW_LINES} eventos, ${FINAL_RAW_SIZE} bytes)"

        echo "--- ${TASK_NAME} iter#${ITERATION} [${CLAUDE_START} -> ${CLAUDE_END}] ---" >> "$TASK_LOG"
        cat "$CLAUDE_READABLE" >> "$TASK_LOG"
        echo "--- END ---" >> "$TASK_LOG"

        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [READABLE ${TASK_NAME} iter#${ITERATION}]" >> "$MAIN_LOG"
        cat "$CLAUDE_READABLE" >> "$MAIN_LOG"

        if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
            log "[ERRO] Claude retornou codigo ${CLAUDE_EXIT_CODE}. Tentando novamente em 2s..."
            update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$PENDING" "$COMPLETED" "ERRO (code ${CLAUDE_EXIT_CODE})"
            sleep 2
            continue
        fi

        NEW_PENDING=$(count_pending_checkboxes "$TASK_FILE")
        NEW_COMPLETED=$(count_completed_checkboxes "$TASK_FILE")
        CHECKBOXES_RESOLVIDOS=$((NEW_COMPLETED - COMPLETED))

        log "[PROGRESSO] Antes: ${COMPLETED}c/${PENDING}p | Depois: ${NEW_COMPLETED}c/${NEW_PENDING}p | Diff: +${CHECKBOXES_RESOLVIDOS}"

        if [ "$NEW_PENDING" -eq "$PENDING" ]; then
            log "[ALERTA] Nenhum checkbox foi resolvido nesta iteracao!"
        fi

        sleep 3
    done

    if [ "$PENDING" -ne 0 ]; then
        log "LIMITE DE ITERACOES ATINGIDO para ${TASK_NAME}!"
        update_status "$TASK_NAME" "$TASK_RELPATH" "$ITERATION" "$PENDING" "$COMPLETED" "FALHA - limite"
        exit 1
    fi
done

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VERIFICACAO FINAL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXEC_END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log ""
log "======================================================"
log "TODAS AS TAREFAS DE DOCUMENTACAO CONCLUIDAS!"
log "Inicio: ${EXEC_START_TIME}"
log "Fim:    ${EXEC_END_TIME}"
log "======================================================"
log ""
log "Verificacao final sugerida:"
log "  cd ${PROJECT_ROOT}"
log "  pip install -e '.[docs]'"
log "  mkdocs build --strict"
log "  mkdocs serve"

update_status "TODAS" "N/A" "N/A" "0" "N/A" "CONCLUIDO - ${EXEC_END_TIME}"
exit 0
