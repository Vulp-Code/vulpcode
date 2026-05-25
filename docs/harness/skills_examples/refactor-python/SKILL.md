---
name: refactor-python
description: Applies safe refactoring to Python code (rename, extract, inline) preserving
  behavior. Use when the user asks to "refactor", "extract function", or "rename" in a .py file.
tools_allow: [Read, Edit, Write, Grep, Glob, Bash]
---

# Refactor Python

When refactoring Python code:

1. Always read the file before editing — never modify blindly.
2. Run `python -m pytest <test_file>` before and after to confirm behavior is preserved.
3. For renames: use Grep to find all call sites before changing the definition.
4. For extract-function: verify the extracted function is called correctly in its new form.
5. Prefer Edit over Write for targeted changes; use MultiEdit for atomic multi-site changes.
6. If no tests exist, note it to the user before proceeding.
7. Never change logic while refactoring — separate concerns across commits/steps.

## Examples

```
User: refatore a função `process_data` para extrair a lógica de validação
→ Read the file, identify validation logic, extract to `_validate_data`, update call site, run tests.

User: renomeie `calc_total` para `compute_order_total` em todo o projeto
→ Grep for all occurrences, update definition and all call sites, run tests.
```
