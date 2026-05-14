# Debugar bug

> **Cenario**: voce reproduziu um bug (ou recebeu um stack trace) e quer
> ajuda investigando, isolando a causa e aplicando a correcao com teste de
> regressao.
> **Tempo estimado**: 15-45 minutos para um bug com reproducao confiavel;
> bugs intermitentes podem levar mais tempo.
> **Provider recomendado**: Anthropic (Claude Sonnet/Opus) para raciocinio
> sobre causa raiz; OpenAI (`gpt-5`) tambem funciona bem; Ollama
> (`qwen2.5-coder:7b`) quando o codigo nao pode sair da maquina.

## Contexto

Debug feito sob pressao tende a pular o passo mais importante: **reproduzir
o bug de forma deterministica**. Sem reproducao, qualquer "correcao" e fe.
O fluxo aqui obriga reproduzir, formular hipoteses **antes** de mexer no
codigo, validar a hipotese, corrigir e fixar com teste de regressao. Voce
dirige o escopo — o agente apenas mantem disciplina.

> **Modo recomendado:** `--auto` para esse fluxo. O loop reproduzir →
> testar → corrigir tem muitas tools encadeadas, e cada confirmacao
> manual quebra o ritmo. Veja
> [Modos de permissao](../user-guide/permission-modes.md).

## Passos

### 1. Reproduzir

Antes de qualquer coisa, capture o stack trace exato:

```text
> rode o comando que reproduz o bug. capture o stack trace completo (incluindo arquivos e linhas). nao tente corrigir nada ainda — so me devolva a saida bruta.
```

Se voce ainda nao sabe o comando, peca uma reproducao minima:
`> me ajude a achar a menor sequencia que dispara esse erro: <descricao>`.

### 2. Investigar a linha do erro

```text
> leia o arquivo na linha do erro do stack trace. me diga: 1) o que essa linha esta tentando fazer, 2) que estado precondiciona ela funcionar, 3) o que pode ter causado a falha. nao proponha correcao ainda.
```

Pedir o **estado precondicionado** evita o agente saltar para "trocar
`==` por `is`" quando o problema real e um dict que chega vazio.

### 3. Hipoteses

```text
> liste 3 hipoteses para o bug, ordenadas pela mais provavel. para cada uma: 1) qual o gatilho, 2) que evidencia a confirma ou nega, 3) que teste rapido distinguiria essa hipotese das outras.
```

Tres e o numero magico — duas viram falsa dicotomia, cinco viram
ruido. Se o agente listar mais, peca para podar para tres.

### 4. Validar a hipotese mais provavel

```text
> teste a primeira hipotese: <descrever teste — ex: imprimir o valor de X antes da linha Y, ou rodar com input Z>. se confirma, propoe correcao com diff; se nega, passe para a segunda hipotese e repita.
```

Validar uma de cada vez impede o agente de "consertar tudo" e mascarar
o bug real com mudancas paralelas. Se a primeira hipotese cair, o
agente naturalmente itera para a segunda.

### 5. Aplicar a correcao

```text
> aplique a correcao proposta. depois rode os testes (pytest -q ou o runner do projeto — confira pyproject.toml se duvidar) e me mostre a saida bruta. se algum teste falhou, mostre o erro antes de mexer.
```

Pedir "saida bruta" evita o agente esconder uma falha sob "ajustei tudo".

### 6. Teste de regressao

```text
> escreva um teste em tests/ que falharia com o codigo antigo e passa com o codigo novo. nome no formato test_<funcao>_<cenario_do_bug>. rode `git stash`, confirme que o teste falha, depois `git stash pop` e confirme que passa.
```

Esse teste e o ativo permanente do debug — sem ele, o bug volta no
proximo refactor. O `git stash` valida que a regressao realmente foi
fixada (e nao um teste tautologico).

---

## Variantes

### Bug intermitente (heisenbug)

Quando reproduzir e a parte dificil:

```text
> rode o comando 50 vezes em loop e conte falhas vs sucessos: `for i in $(seq 1 50); do <comando> 2>&1 | tail -5; done`. me devolva a taxa de falha e os ultimos stack traces. depois proponha o que pode estar causando a nao-determinismo (ordem de dict, race, timezone, fixture compartilhada).
```

Causas tipicas: ordem de dict (Python <3.7), `set()` iteration, threads,
clock skew, fixture nao isolada (`tmp_path` vs `/tmp`).

### Bug em producao sem reproducao local

```text
> tenho esse stack trace: <colar trace>. nao consigo reproduzir local. leia os arquivos das ultimas 3 frames e me diga: 1) que pre-condicoes precisam ser verdadeiras para esse trace acontecer, 2) que dados podem estar faltando da minha reproducao, 3) que log adicional eu posso adicionar para confirmar quando bater de novo.
```

Bug-de-producao costuma vir de input que voce nao prevê — peca ao
agente para listar as **assumptions** da funcao falhada.

### Bug em dependencia (lib externa)

```text
> o stack trace mostra que a falha e dentro de `lib_x/internal.py`. confira se a versao instalada esta atualizada (`pip show lib_x`). depois leia o changelog/issues recentes (use a tool WebFetch com a URL do repo) e me diga se ja e bug conhecido.
```

> Se `WebSearch` estiver indisponivel (mensagem
> `WebSearch backend unavailable`), use [`WebFetch`](../tools/web.md)
> direto na URL conhecida.

### Bisect com git

Para bugs que apareceram "do nada":

```text
> use git bisect para achar o commit que introduziu o bug. comeca com bom=v1.2.0 e ruim=HEAD. para cada commit, rode <comando-de-reproducao>. me devolva o commit ofensor e o diff dele.
```

---

## Anti-patterns / armadilhas

- **Pedir "conserte tudo" sem reproduzir o bug**: o agente vai inferir
  causas plausiveis e mexer em codigo nao relacionado. Sem reproducao,
  voce nao tem como verificar se a "correcao" funcionou.
- **Aceitar a primeira correcao sem validar**: o agente as vezes acerta na
  hipotese mas erra no diff. Sempre rode os testes (e o teste de
  regressao do passo 6) antes de fechar.
- **Mexer em codigo de producao para o teste passar**: se um teste cobre
  o bug e ele falha, o conserto e em producao, nao no teste. Isso e um
  caso especial do mesmo anti-pattern em
  [Escrever testes](write-tests.md).
- **Pedir o agente para "adicionar logs em todo lugar"**: estoura
  `max_tokens` e poluiu o codigo. Pe logs em pontos especificos
  derivados da hipotese.
- **Ignorar o stack trace ("o erro nao e isso")**: stack trace nao mente
  sobre **onde** falhou. Se a mensagem parece confusa, e provavel que
  uma camada acima esta engolindo a excecao real — peca:
  `> ache onde essa excecao e capturada (try/except) e veja se algum bloco engole sem relogar`.
- **Confiar em `WebSearch` para erros obscuros**: a tool pode estar
  indisponivel. Use [`WebFetch`](../tools/web.md) com URL de
  GitHub/StackOverflow conhecida.

---

## Veja tambem

- [Escrever testes](write-tests.md) — o passo 6 (regressao) e mais
  facil se o modulo ja tem cobertura.
- [Refatorar codigo](refactor-code.md) — quando o bug expoe um problema
  estrutural maior.
- [Tools / Busca e Shell](../tools/search-and-shell.md) — `Bash` para
  rodar reproducoes, `Grep` para achar onde excecoes sao capturadas.
- [Tools / Web](../tools/web.md) — `WebFetch` para puxar issues e
  changelogs de libs.
- [Modos de permissao](../user-guide/permission-modes.md) — `--auto` no
  loop reproducao/teste, `--plan` se quiser so a hipotese sem mexer.
- [Slash commands](../user-guide/slash-commands.md) — `/save` para
  guardar a sessao se o debug ficar longo.
