# Validated Write family

A familia `Write*` especializada fornece 15 tools de criacao de arquivo com **validacao
embutida** e **gravacao atomica**. Cada tool valida o conteudo antes de gravar no disco;
se a validacao falhar, o arquivo nunca e criado ou modificado, e uma mensagem de erro
precisa (linha, coluna, trecho de contexto) e devolvida ao modelo para que ele possa
corrigir e tentar novamente.

---

## 1. Why a family

A tool generica `Write` (veja [Filesystem](filesystem.md)) grava qualquer conteudo sem
inspecionar o formato. Isso e util para arquivos de texto livre, mas problematico para
codigo e formatos estruturados: um `.py` com `SyntaxError` ou um `.json` malformado sao
gravados silenciosamente, e o erro so aparece quando o arquivo e usado.

A familia `Write*` inverte essa ordem:

1. **Valida primeiro** — executa o validador especifico do tipo (AST parse, JSON parse,
   schema check, etc.) sobre o conteudo recebido do modelo.
2. **So grava se passar** — usa gravacao atomica (tmp + rename) para garantir que ou o
   arquivo valido existe, ou o arquivo anterior permanece intacto.
3. **Retorna erro acionavel** — linha, coluna e snippet de 3 linhas ao redor do problema,
   para que o modelo possa corrigir e reenviar.

Resultado: o loop agentico pode criar arquivos validos autonomamente, mesmo quando o
modelo gera codigo com erros na primeira tentativa.

---

## 2. Common contract

Todas as tools da familia seguem o mesmo contrato:

- **Input obrigatorio:** `file_path: str` e `content: str`.
- **Validacao** ocorre em memoria, antes de qualquer escrita em disco.
- **Em caso de erro de validacao:** `ToolResult(is_error=True)` com mensagem detalhada;
  o disco nao e modificado.
- **Em caso de sucesso:** gravacao atomica via arquivo temporario + `os.replace()`;
  `ToolResult(output="Wrote N bytes to <path> (validated OK)")`.
- **Dependencias opcionais** sao importadas de forma lazy (dentro de `validate()`); se
  nao instaladas, a tool retorna `is_error=True` com instrucao de `pip install`.
- **Diretorios pais** sao criados automaticamente (`parents=True, exist_ok=True`).

Codigo base compartilhado: [`src/vulpcode/tools/_validated_write.py`](https://github.com/vulpcode/vulpcode/blob/main/src/vulpcode/tools/_validated_write.py).

---

## 3. Tool reference

| Tool        | Tipo de arquivo | Validador                                    | Dependencia opcional       |
|-------------|-----------------|----------------------------------------------|----------------------------|
| `WritePy`   | `.py`           | `ast.parse`                                  | —                          |
| `WriteIpynb`| `.ipynb`        | `nbformat.validate` + `ast.parse` por celula | `nbformat`                 |
| `WriteMd`   | `.md`           | `markdown-it` + fences balanceadas           | `markdown-it-py`           |
| `WriteDocx` | `.docx`         | round-trip via `python-docx`                 | `python-docx`              |
| `WritePdf`  | `.pdf`          | round-trip via `pypdf`                       | `weasyprint` OR `reportlab` + `pypdf` |
| `WriteJson` | `.json`         | `json.loads`                                 | —                          |
| `WriteYaml` | `.yaml` / `.yml`| `yaml.safe_load`                             | `PyYAML`                   |
| `WriteToml` | `.toml`         | `tomllib.loads`                              | —                          |
| `WriteCsv`  | `.csv`          | `csv.reader` + verificacao de colunas        | —                          |
| `WriteXml`  | `.xml`          | `xml.etree.ElementTree.fromstring`           | —                          |
| `WriteHtml` | `.html`         | `html.parser` (leniente) / `lxml` (estrito) | `lxml` (modo estrito)      |
| `WriteSh`   | `.sh`           | `bash -n`                                    | — (requer bash no PATH)    |
| `WriteSql`  | `.sql`          | `sqlparse` + balanco de parenteses/aspas     | `sqlparse`                 |
| `WriteSvg`  | `.svg`          | parse XML + verificacao da tag raiz          | —                          |
| `WriteDot`  | `.dot`          | `pydot.graph_from_dot_data`                  | `pydot`                    |

Para instalar todas as dependencias opcionais de uma vez:

```bash
pip install "vulpcode[docs-tools]"
```

---

## 4. Atomic save

A gravacao atomica garante que nenhum arquivo parcialmente escrito ou invalido chega ao
disco:

```
content (em memoria)
       |
       v
[validacao] --falha--> ToolResult(is_error=True)  [disco intacto]
       |
    sucesso
       |
       v
<path>.tmp  <-- write_text (UTF-8)
       |
       v
os.replace(<path>.tmp, <path>)   # operacao atomica no mesmo filesystem
       |
       v
ToolResult(output="Wrote N bytes to <path> (validated OK)")
```

`os.replace` e atomico em sistemas POSIX (rename(2)); em Windows, e atomic-o-suficiente
para uso pratico. Se o processo for morto entre a escrita do `.tmp` e o rename, o `.tmp`
pode sobrar — mas o destino final permanece intacto (ou inexistente). Nao ha residuais
visiveis para o usuario.

---

## 5. Auto-repair loop

Quando combinada com o provider [`internal-llm-agentic`](../providers/internal-llm-agentic.md),
a familia `Write*` participa do loop de reparo automatico:

1. Modelo emite conteudo com erro de sintaxe.
2. `Write*` valida, detecta o erro, retorna `is_error=True` com linha e coluna.
3. Agent loop injeta o erro de volta na conversa.
4. Modelo emite versao corrigida.
5. Loop repete ate validar OK ou atingir `max_iters`.

O resultado final e sempre um arquivo valido no disco, ou uma mensagem clara ao usuario
explicando por que nao foi possivel corrigir.

Para detalhes e exemplo passo-a-passo, veja
[Repair loop](../providers/internal-llm-agentic.md#4-repair-loop).

---

## Veja tambem

- [Filesystem](filesystem.md) — `Write` generica e outras tools de arquivo
- [internal-llm-agentic](../providers/internal-llm-agentic.md) — provider que ativa o loop de reparo
- [Tools (visao geral)](index.md)
