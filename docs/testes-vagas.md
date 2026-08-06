# Testes com vagas reais (inHire)

Matriz de validação do site `inhire` usando vagas reais em modo debug (nada é enviado).

## Como rodar

```bash
make apply SITE=inhire URL=<url-da-vaga> DEBUG=1
```

`DEBUG=1` abre o navegador visível, preenche o formulário, dispara o alerta de sucesso e **não envia** a candidatura.

## Matriz de vagas testadas

| # | Vaga | Domínio | Diferenças de formulário | Resultado |
|---|---|---|---|---|
| 1 | Consultor de Negócios/Vendas SP | `portal.inhire.app` | com país/cidade, pretensão, indicação; sem linkedin; sem diversidade | ✅ relatório limpo |
| 2 | Estágio Dev Full Stack | `v360.inhire.app` | com linkedin e diversityGroup; sem pretensão; sem gênero/orientação/raça | ✅ relatório limpo |
| 3 | Técnico de Segurança do Trabalho BH | `infotecbrasil.inhire.app` | sem país/cidade/indicação; com diversidade completa (gênero, orientação, raça) | ✅ relatório limpo |

Todas as três concluíram com `[RELATORIO] Todos os campos visíveis estão preenchidos.`

## Comportamento observado

Cada vaga renderiza um subconjunto diferente de campos. O script se adapta automaticamente:

- **Campos presentes** → preenchidos com `[CAMPO] <nome> | status=ok`.
- **Campos ausentes** → `[CAMPO-NAO-ENCONTRADO] <nome> | obrigatorio=False` e o fluxo segue.
- **Obrigatório de verdade** (nome completo) → aborta com erro claro se não existir na página.
- **Disponibilidade presencial** → não é mais bloqueante: se a vaga não tiver a pergunta, é ignorada após as tentativas e o fluxo segue.
- **Avançar/Submit** → habilitados naturalmente quando os obrigatórios são preenchidos; fallback via JS apenas em casos extremos.

## Logs de referência

### Vaga 2 (v360) — trecho

```
[FLUXO] site=inhire | url=https://v360.inhire.app/vagas/9865a22d-9a7d-4d11-b5f5-cfd5d90a1201/...
[CAMPO] nome | status=ok | seletor=input[name='name']
[CAMPO] linkedin | status=ok | seletor=input[name='linkedinUsername']
[CAMPO] cidade | status=ok | valor='Sao Jose - SC'
[CAMPO-NAO-ENCONTRADO] pretensao-salarial | valor='4500' | obrigatorio=False
[CAMPO] avancar | status=ok
[CAMPO] diversityGroup | status=ok | texto='Prefiro não responder'
[FLUXO] submit | status=debug-nao-enviado (alerta de sucesso exibido)
[RELATORIO] Todos os campos visíveis estão preenchidos.
```

### Vaga 3 (infotecbrasil) — trecho

```
[CAMPO] linkedin | status=ok | seletor=input[name='linkedinUsername']
[CAMPO] pais | status=nao-encontrado
[CAMPO] cidade | status=nao-encontrado (gatilho)
[CAMPO] indicacao-nao | status=nao-encontrado
[CAMPO] avancar | status=ok
[CAMPO] genero | status=ok | opcao='Prefiro não responder'
[CAMPO] orientacao | status=ok | opcao='Prefiro não responder'
[CAMPO] raca | status=ok | opcao='Prefiro não responder'
[RELATORIO] Todos os campos visíveis estão preenchidos.
```

## Como usar este documento

- **Validação:** ao alterar o script do site, rode as 3 vagas e confira que todas terminam com relatório limpo.
- **Novas vagas:** ao encontrar uma vaga com campos que o script não conhece, adicione-a na matriz com o log de saída — o `[CAMPO-NAO-PREENCHIDO]`/`[ERRO-CAMPO]` aponta o ajuste necessário.
- **IA:** cole o bloco de logs de uma vaga problemática em uma IA com o prompt do README para gerar o ajuste das regras.

---

# Teste com vaga real (Quickin)

Validação do site `quickin` (jobs.quickin.io) com a vaga do IESDE em modo headless
**sem enviar** candidatura (submit neutralizado durante a validação).

## Como rodar (modo debug, não envia)

```bash
make apply SITE=quickin URL="https://jobs.quickin.io/iesde/jobs/<id>?src=Indeed" DEBUG=1
```

`DEBUG=1` abre o navegador visível, preenche o formulário, dispara o alerta de sucesso e
**não envia** a candidatura.

## Vaga validada

| # | Vaga | Domínio | Diferenças de formulário | Resultado |
|---|---|---|---|---|
| 1 | Desenvolvedor de Software Sênior – Foco em Produto (IESDE, PJ/Remoto) | `jobs.quickin.io` | formulário único (sem abas); datepicker de nascimento; gênero/PcD; endereço; consentimento LGPD | ✅ todos os campos preenchidos |

## Comportamento observado

- **SPA (Nuxt):** o botão "Candidatar" pode demorar a renderizar; o script reavalia o
  seletor com retry e só então clica (navega para `/iesde/apply?job_id=...`).
- **Idioma:** o site serve UI em inglês ("Apply") se o `Accept-Language` não for pt-BR.
  O engine agora cria o contexto com `locale="pt-BR"` e o módulo aceita ambos os textos.
- **Data de nascimento:** input readonly do `vuedatepicker`; o calendário abre direto na
  visão de ano — o script navega a faixa de anos, clica ano → mês → dia.
- **Currículo:** após o upload o componente Vue substitui o `<input type=file>` por um
  aviso com o nome do arquivo (o arquivo fica no estado do componente e é enviado no
  payload do submit). O script não depende do input continuar no DOM.
- **Submit:** botão "Finalizar" (`button[type='submit']`), sempre habilitado; validação
  JS exige nome, nascimento, gênero, e-mail, telefone, currículo e consentimento — todos
  preenchidos pelo script. Em debug nada é enviado.

## Logs de referência (validação headless, submit neutralizado)

```
[FLUXO] site=quickin | url=https://jobs.quickin.io/iesde/jobs/6a732a038e38610013d39d59?src=Indeed
[CAMPO] nome | status=ok | seletor=#name
[CAMPO] cargo_pretendido | status=ok | seletor=#headline
[CAMPO] data_nascimento | status=ok | valor='15/03/1990'
[CAMPO] genero | status=ok | seletor=#female
[CAMPO] email | status=ok | seletor=#email
[CAMPO] telefone | status=ok | seletor=input[placeholder='00 00000-0000']
[CAMPO] pais | status=ok | valor='BR'
[CAMPO] estado | status=ok | seletor=#region
[CAMPO] cidade | status=ok | seletor=#city
[CAMPO] bairro | status=ok | seletor=#neighborhood
[CAMPO] endereco | status=ok | seletor=#address
[CAMPO] cep | status=ok | seletor=#zipcode
[CAMPO] resumo | status=ok | seletor=#summary
[CAMPO] curriculo | status=ok
[CAMPO] consentimento | status=ok
[FLUXO] submit | status=debug-nao-enviado (alerta de sucesso exibido)
```

Valores conferidos no DOM após o preenchimento: `nome`, `nascimento=15/03/1990`,
`genero=female`, `email`, `telefone`, `cidade`, `estado`, `cep`, `curriculo_anexado=curriculo.pdf`,
`consentimento=True`, `pais=BR`.
