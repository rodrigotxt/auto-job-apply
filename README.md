# auto-job-apply

Biblioteca open-source para automação de candidaturas, extraída e refatorada a partir do [JobSpy](https://github.com/rodrigotxt/JobSpy).

## Objetivo

Fornecer uma interface unificada (`apply`) para automatizar a submissão de currículos em diversos sites de emprego, facilitando contribuições da comunidade.

## Principais características

- **Interface única:** `apply(site, url_vaga, dados, curriculo_path)` — mesma função usada pelo Makefile, testes e consumidores externos.
- **Extensível:** registro explícito de sites via decorator + `make add-site`.
- **Resiliente:** fallback de seletores, busca por label e relatório de campos não preenchidos.
- **Logs estruturados:** saída parseável por máquina/IA para auto-aprimoramento do script.
- **Qualidade:** testes com DOM mockado (sem navegador real).
- **Segurança:** sem dados pessoais no repositório — use dados fictícios nos exemplos.

## Documentação

- [`docs/testes-vagas.md`](docs/testes-vagas.md) — matriz de validação com vagas reais (inHire).

## Quick start

```bash
make up        # cria .venv, instala dependências e o Chromium do Playwright
make help      # lista todos os comandos
```

## Uso

### Rodar uma candidatura (modo real)

```bash
make apply SITE=inhire URL=https://portal.inhire.app/vagas/<id>/<slug>
```

Envia a candidatura de verdade. Os dados do candidato vêm de `assets/dados-de-candidatura.yaml` e o currículo de `assets/curriculo.pdf`.

### Modo interativo

```bash
make apply
```

Se `SITE`/`URL` não forem passados, o comando pergunta interativamente:

1. **Site** — lista os sites registrados (escolha por número ou nome);
2. **URL da vaga** — validada como `http(s)://`;
3. **Modo debug** — pergunta se quer rodar sem enviar (recomendado para validar);
4. **Confirmação final** — no modo real, pede confirmação explícita antes de enviar (default é não).

> Em modo não interativo (sem terminal, ex.: CI), `SITE` e `URL` continuam obrigatórios.

### Rodar em modo debug (não envia nada)

```bash
make apply SITE=inhire URL=<url> DEBUG=1
```

- Navegador **visível**, com delay de 2s por campo preenchido.
- **Não envia a candidatura**: ao final dispara `alert('Vaga preenchida com sucesso! Confira.')` e mantém o navegador aberto por 10s.
- Útil para validar o fluxo e conferir os campos antes de um envio real.

### Testes e lint

```bash
make test      # pytest (DOM mockado)
make lint      # ruff
```

### Demo da saída da função (não envia nada)

```bash
make demo      # usa uma vaga inHire padrão
# ou: make demo SITE=inhire URL=<url>
```

Mostra em tempo real cada evento JSON de `on_progress` (status/etapa/campo) e o dict de retorno final com `status`, `log` e `duracao_seg`.

### Adicionar um novo site

```bash
make add-site NAME=novosite
```

Cria o arquivo em `src/auto_job_apply/sites/novosite.py` com o boilerplate e o registra no `__init__.py`.

## Saída da função

A função `apply` **nunca levanta exceção**: sempre retorna um dict com o resultado final e, opcionalmente, emite eventos de progresso em tempo real via callback `on_progress`.

### Eventos de progresso (`on_progress`)

```python
from auto_job_apply import apply

def on_progress(evt: dict):
    # evt é serializável em JSON — persista onde quiser (banco, kanban, Redis)
    print(evt)

resultado = apply(site, url, dados, curriculo, on_progress=on_progress)
```

Cada campo/etapa emite um evento `{status, etapa, timestamp, ...}`:

```json
{"status": "processing", "etapa": "started",   "timestamp": 1725300000.1, "site": "inhire", "url": "..."}
{"status": "processing", "etapa": "navegacao", "status_campo": "ok"}
{"status": "processing", "etapa": "campo",     "campo": "nome", "status_campo": "ok", "seletor": "input[name='name']"}
{"status": "processing", "etapa": "campo",     "campo": "linkedin", "status_campo": "nao-encontrado"}
{"status": "processing", "etapa": "avancar",   "status_campo": "ok"}
{"status": "processing", "etapa": "submit",    "status_campo": "ok"}
{"status": "completed",  "etapa": "concluido", "duracao_seg": 42.3}
```

Em caso de falha:

```json
{"status": "error", "etapa": "erro", "erro": "Page.click: Timeout...", "duracao_seg": 12.1}
```

Status possíveis: `processing` → `completed` ou `error`. Falhas no callback nunca quebram a automação.

### Retorno final

```python
{
  "status": "completed",        # ou "error"
  "site": "inhire",
  "url": "https://...",
  "log": "[FLUXO] site=inhire | ...\n[CAMPO] nome | status=ok | ...",  # logs estruturados (mesmos do terminal, servem para IA)
  "duracao_seg": 42.3,
  "erro": "mensagem legível",  # presente apenas quando status == "error"
}
```

### Exemplo num fluxo contínuo (Celery/JobSpy)

```python
def task_candidatura(vaga_id, site, url, dados, curriculo):
    def on_progress(evt):
        db.atualizar_status(vaga_id, evt["status"], etapa=evt["etapa"])

    resultado = apply(site, url, dados, curriculo, on_progress=on_progress)
    db.salvar_log(vaga_id, resultado["log"])
    return resultado
```

## Arquitetura

```
src/auto_job_apply/
├── __init__.py      # interface pública apply()
├── engine.py        # BrowserEngine: Playwright + retry + fallbacks
├── registry.py      # SITES_REGISTRY + decorator register_site
└── sites/           # um arquivo por site (gupy, inhire, ...)
```

- **`engine.py`** — abstrai o Playwright: `click`, `fill_field`, `force_upload`, `check`, `type_text`, `evaluate`, `campo_por_label`, `relatorio_campos_nao_preenchidos`. Todas as interações têm retry limitado (3 tentativas, 1s entre elas).
- **`registry.py`** — mapeamento explícito nome do site → função executor. Novo site = novo arquivo + registro (nunca convenção por nome de arquivo).
- **`sites/*.py`** — implementam `apply_<site>(engine, url_vaga, dados, curriculo_path) -> bool`.

## Logs estruturados (formato para IA)

O script emite logs no formato `[MARCADOR] campo | chave=valor` — cada linha é auto-contida e pensada para ser **jogada numa IA** que ajusta as regras do script.

### Marcadores

| Marcador | Significado |
|---|---|
| `[FLUXO]` | Etapas do fluxo: navegação, avançar, submit, conclusão. |
| `[CAMPO]` | Resultado de um campo: `status=ok`, `status=erro`, `status=nao-encontrado`, `status=resolvido-por-label`. |
| `[ERRO-CAMPO]` | Falha ao preencher um campo (aborta o fluxo apenas se o campo for obrigatório). |
| `[CAMPO-NAO-ENCONTRADO]` | Campo não existe no DOM daquela vaga (opcionais seguem; só o nome completo é obrigatório e aborta). |
| `[CAMPO-NAO-PREENCHIDO]` | Campo visível que ficou vazio, detectado no relatório final. |
| `[RELATORIO]` | Resumo final: `Todos os campos visíveis estão preenchidos.` ou `N campo(s) não preenchido(s):`. |

### Exemplo de saída

```
[FLUXO] site=inhire | url=https://portal.inhire.app/vagas/<id>/<slug>
[CAMPO] nome | status=ok | seletor=input[name='name']
[CAMPO-NAO-ENCONTRADO] linkedin | valor='candidata-exemplo' | obrigatorio=False
[CAMPO] cidade | status=ok | valor='Sao Jose - SC'
[CAMPO] disponibilidade-presencial | status=ok | seletor=input[name='workModel'][value='true']
[CAMPO] avancar | status=ok
[CAMPO] pcd | status=ok | opcao='Não'
[FLUXO] submit | status=debug-nao-enviado (alerta de sucesso exibido)
[RELATORIO] Todos os campos visíveis estão preenchidos.
```

Exemplo com pendências (o que a IA deve corrigir):

```
[ERRO-CAMPO] disponibilidade-presencial | seletor=input[name='workModel'][value='true'] | erro=Page.click: Timeout...
[RELATORIO] 1 campo(s) visível(is) não preenchido(s):
[CAMPO-NAO-PREENCHIDO] OBRIGATORIO | label='Disponibilidade para trabalho presencial' | name='workModel' | id='None' | tag=input type=radio
```

### Como usar com IA

Cole o bloco de logs (do `[FLUXO]` até o `[RELATORIO]`) e peça, por exemplo:

> *"Ajuste as regras do script de automação para preencher os campos apontados nos logs. Para cada `[CAMPO-NAO-PREENCHIDO]` ou `[ERRO-CAMPO]`, corrija o seletor ou a lógica."*

Os logs dizem **qual** campo falhou, **por quê** e **qual seletor** foi usado — o suficiente para iterar as regras sem depender de inspeção manual do DOM.

## Resiliência

Cada campo é preenchido em camadas, nesta ordem:

1. **Seletores candidatos** — lista de seletores por campo, em ordem de preferência (`_CAMPOS` no site).
2. **Fuzzy por label** — se nenhum seletor casar, busca o campo pelo texto visível do label/placeholder/aria-label.
3. **Retry** — toda interação tenta até 3 vezes com 1s de espera (campos que renderizam após interação, ex.: dropdown que só existe depois de abrir).
4. **Fallback JS** — elementos realmente ocultos (checkbox/dropdown estilizados) são acionados via JavaScript.
5. **Relatório final** — sempre roda (até em erro, via `finally`) e lista o que ficou vazio.

Campos **obrigatórios** (apenas o nome completo hoje) abortam o fluxo com `[ERRO-CAMPO]`/`[CAMPO-NAO-ENCONTRADO]` explícito; os demais — inclusive disponibilidade presencial — são ignorados com warning quando ausentes e o fluxo segue.

## Segurança

- O repositório é **público**: nunca commitar dados pessoais, currículos reais ou credenciais.
- `assets/` contém apenas **dados fictícios** de exemplo.
- Dados do candidato ficam em `assets/dados-de-candidatura.yaml` (não versionar dados reais).

## Licença

Apache License 2.0
