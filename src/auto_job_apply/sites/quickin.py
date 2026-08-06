"""Automação do site Quickin (jobs.quickin.io).

Fluxo observado (template IESDE, ago/2026):

1. Página da vaga (`jobs.quickin.io/<empresa>/jobs/<id>`) com botão "Candidatar".
2. O clique navega para `/iesde/apply?job_id=<id>` — formulário único em uma
   página só (sem abas), com as seções: Foto, Dados básicos, Contato, Endereço,
   Resumo das qualificações, Currículo e consentimento LGPD.
3. Submissão pelo botão "Finalizar" (`button[type='submit']`).

Particularidades do formulário:

- "Data de nascimento" é um datepicker (vuedatepicker) com input readonly.
  O clique abre o calendário direto na VISÃO DE ANO; é preciso navegar a
  faixa de anos, clicar o ano, o mês e então o dia.
- "Gênero" e "PcD" são radios/checkboxes com IDs estáveis.
- "País" é um <select> nativo (Brasil = value "BR").
- Telefone tem campo de DDI (default +55) + input de número.
- Só o checkbox de consentimento tem `required` HTML; os demais obrigatórios
  (nome, data de nascimento, gênero, e-mail, telefone, currículo) são
  validados por JS no submit.
"""

import logging
import re
import time

from ..engine import BrowserEngine
from ..progresso import STATUS_PROCESSING
from ..registry import register_site
from ..schema import normalizar, obter

logger = logging.getLogger(__name__)

# Botão de candidatura na página da vaga (pode ser <a> ou <button>; o texto
# varia com o idioma servido — "Candidatar" (pt-BR) ou "Apply" (en-US))
_SELETORES_CANDIDATAR = [
    "a:has-text('Candidatar')",
    "button:has-text('Candidatar')",
    "a:has-text('Apply')",
    "button:has-text('Apply')",
]

# Alternativas de seletor para o botão de submit
_SELETORES_SUBMIT = [
    "button[type='submit']:has-text('Finalizar')",
    "button[type='submit']",
]

# Seletores candidatos por campo (IDs estáveis do template)
# Chaves em inglês, no padrão do schema.py (dados_candidatura)
_CAMPOS = {
    "full_name": ["#name"],
    "desired_role": ["#headline"],
    "birth_date": ["#birth_date input"],
    "email": ["#email"],
    "phone": ["input[placeholder='00 00000-0000']"],
    "country": ["#country"],
    "state": ["#region"],
    "city": ["#city"],
    "neighborhood": ["#neighborhood"],
    "address": ["#address"],
    "zip_code": ["#zipcode"],
    "summary": ["#summary"],
    "resume": ["#validatedCustomFile"],
    "consent": ["#consent"],
}

# Gênero: valor aceito no YAML -> id do radio no formulário
# (aceita inglês, padrão do schema, e português por compatibilidade)
_GENEROS = {
    "male": "male",
    "masculino": "male",
    "female": "female",
    "feminino": "female",
    "other": "other",
    "outros": "other",
    "outro": "other",
    "prefer_not_to_say": "prefer_not_to_say",
    "prefiro não dizer": "prefer_not_to_say",
    "prefiro nao dizer": "prefer_not_to_say",
}

# PcD: valor aceito no YAML (lista) -> id do checkbox no formulário
_PCD = {
    "hearing": "hearing",
    "auditiva": "hearing",
    "vision": "vision",
    "visual": "vision",
    "intellectual": "intellectual",
    "intelectual": "intellectual",
    "physical": "physical",
    "física": "physical",
    "fisica": "physical",
}

# Nomes dos meses exibidos no calendário (pt-BR)
_MESES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


# Campos de dados_candidatura (schema.py) usados por este site — o
# `make check-dados SITE=quickin` usa esta lista para sugerir o que falta.
_CAMPOS_USADOS = [
    "full_name",
    "desired_role",
    "headline",
    "birth_date",
    "disabilities",
    "gender",
    "email",
    "phone",
    "country",
    "state",
    "city",
    "neighborhood",
    "address",
    "zip_code",
    "summary",
    "consent",
]


class CampoNaoEncontradoError(ValueError):
    """Campo obrigatório não encontrado no formulário."""


class SubmitBloqueadoError(RuntimeError):
    """Não foi possível submeter a candidatura."""


def _so_digitos(valor) -> str:
    """Remove tudo que não for dígito."""
    return "".join(c for c in str(valor) if c.isdigit())


def _exigir_nome_completo(dados: dict) -> str:
    """Valida que o candidato informou nome e sobrenome."""
    nome = str(obter(dados, "full_name", "")).strip()
    if len(nome.split()) < 2:
        raise ValueError("Campo 'full_name' deve conter nome e sobrenome (ex.: 'Maria Silva').")
    return nome


def _parse_data_nascimento(dados: dict) -> tuple[int, int, int]:
    """Lê 'birth_date' (dd/mm/aaaa) do YAML e devolve (dia, mes, ano)."""
    valor = str(obter(dados, "birth_date", "")).strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", valor)
    if not m:
        raise ValueError(
            "Campo 'birth_date' deve estar no formato dd/mm/aaaa (ex.: '15/03/1990')."
        )
    dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mes <= 12 and 1 <= dia <= 31):
        raise ValueError(f"Campo 'birth_date' inválido: '{valor}' (use dd/mm/aaaa).")
    return dia, mes, ano


def _resolver_campo(engine: BrowserEngine, chave: str) -> str | None:
    """Resolve o seletor do campo (primeiro candidato que existir no DOM)."""
    for sel in _CAMPOS.get(chave, []):
        if engine.exists(sel):
            return sel
    return None


def _log_campo(chave: str, status: str, detalhe: str = ""):
    logger.info(f"[CAMPO] {chave} | status={status} | {detalhe}".rstrip(" |"))


def _emitir_campo(engine: BrowserEngine, chave: str, status: str, seletor: str | None = None):
    """Emite evento de progresso de um campo (etapa='campo')."""
    engine.emitir(STATUS_PROCESSING, "campo", campo=chave, status_campo=status, seletor=seletor)


def _preencher_campo(engine: BrowserEngine, chave: str, valor: str, obrigatorio: bool = False):
    """Preenche um campo de texto com log estruturado e evento de progresso."""
    if not valor:
        _log_campo(chave, "ignorado-valor-vazio")
        _emitir_campo(engine, chave, "ignorado-valor-vazio")
        return
    seletor = _resolver_campo(engine, chave)
    if seletor is None:
        msg = f"[CAMPO-NAO-ENCONTRADO] {chave} | valor='{valor}' | obrigatorio={obrigatorio}"
        _emitir_campo(engine, chave, "nao-encontrado")
        if obrigatorio:
            logger.error(msg)
            raise CampoNaoEncontradoError(msg)
        logger.warning(msg)
        return
    try:
        engine.fill_field(seletor, valor)
        _log_campo(chave, "ok", f"seletor={seletor}")
        _emitir_campo(engine, chave, "ok", seletor=seletor)
    except Exception as e:
        msg = f"[ERRO-CAMPO] {chave} | seletor={seletor} | erro={e}"
        _emitir_campo(engine, chave, "erro", seletor=seletor)
        if obrigatorio:
            logger.error(msg)
            raise
        logger.warning(msg)


def _abrir_formulario(engine: BrowserEngine):
    """Clica em 'Candidatar' (se existir) e aguarda o formulário (#name) carregar.

    A página da vaga é uma SPA (Nuxt): o botão pode demorar a renderizar, então
    o seletor é reavaliado a cada tentativa. Se a URL já for a de candidatura
    direta (sem botão), segue direto.
    """
    for _ in range(engine.max_attempts):
        if engine.exists("#name"):
            return
        for sel in _SELETORES_CANDIDATAR:
            if engine.exists(sel):
                engine.click(sel)
                break
        else:
            time.sleep(engine.retry_delay)
            continue
        # Botão clicado: aguarda o formulário carregar (navegação + render)
        for _ in range(engine.max_attempts):
            if engine.exists("#name"):
                return
            time.sleep(engine.retry_delay)
        break
    raise CampoNaoEncontradoError(
        "[CAMPO-NAO-ENCONTRADO] formulario | Formulário de candidatura não carregou (#name)."
    )


def _selecionar_data_nascimento(engine: BrowserEngine, dados: dict):
    """Seleciona a data de nascimento no datepicker (visão inicial: ano).

    Fluxo: abrir calendário -> navegar faixa de anos -> clicar ano -> mês -> dia.
    O campo é obrigatório no formulário; falha levanta erro.
    """
    chave = "birth_date"
    dia, mes, ano = _parse_data_nascimento(dados)
    seletor = _resolver_campo(engine, chave)
    if seletor is None:
        msg = (
            f"[CAMPO-NAO-ENCONTRADO] {chave} | valor='{dia:02d}/{mes:02d}/{ano}' | "
            "obrigatorio=True"
        )
        _emitir_campo(engine, chave, "nao-encontrado")
        logger.error(msg)
        raise CampoNaoEncontradoError(msg)
    try:
        engine.click(seletor)
        time.sleep(0.5)

        # Navega as faixas de anos até o ano desejado (o calendário abre na visão de ano)
        for _ in range(15):
            faixa = engine.evaluate(
                """() => {
                    const raiz = document.querySelector('#birth_date');
                    if (!raiz) return '';
                    const cals = [...raiz.querySelectorAll('.vdp-datepicker__calendar')];
                    const vis = cals.find(c => getComputedStyle(c).display !== 'none');
                    if (!vis) return '';
                    const sp = vis.querySelectorAll('header span');
                    return sp[1] ? sp[1].textContent.trim() : '';
                }"""
            )
            numeros = re.findall(r"\d+", str(faixa))[:2]
            if len(numeros) < 2:
                raise CampoNaoEncontradoError(
                    "[CAMPO-NAO-ENCONTRADO] data_nascimento | calendário não abriu."
                )
            lo, hi = int(numeros[0]), int(numeros[1])
            if lo <= ano <= hi:
                break
            engine.click(
                "#birth_date .vdp-datepicker__calendar:visible .prev" if ano < lo
                else "#birth_date .vdp-datepicker__calendar:visible .next"
            )
            time.sleep(0.4)
        else:
            raise CampoNaoEncontradoError(
                f"[CAMPO-NAO-ENCONTRADO] data_nascimento | ano {ano} fora das faixas "
                f"navegadas ({faixa})."
            )

        engine.click(f"#birth_date .vdp-datepicker__calendar:visible .cell.year:has-text('{ano}')")
        time.sleep(0.4)
        engine.click(
            f"#birth_date .vdp-datepicker__calendar:visible .cell.month:has-text('{_MESES[mes]}')"
        )
        time.sleep(0.4)
        engine.click(f"#birth_date .vdp-datepicker__calendar:visible .cell.day:has-text('{dia}')")
        time.sleep(0.4)
        _log_campo(chave, "ok", f"valor='{dia:02d}/{mes:02d}/{ano}'")
        _emitir_campo(engine, chave, "ok", seletor=seletor)
    except CampoNaoEncontradoError:
        raise
    except Exception as e:
        msg = f"[ERRO-CAMPO] {chave} | seletor={seletor} | erro={e}"
        _emitir_campo(engine, chave, "erro", seletor=seletor)
        logger.error(msg)
        raise


def _selecionar_genero(engine: BrowserEngine, dados: dict):
    """Marca o radio de gênero (obrigatório). Default: 'Prefiro não dizer'."""
    chave = "gender"
    valor = obter(dados, "gender", "prefer_not_to_say")
    radio_id = _GENEROS.get(str(valor).strip().lower(), "prefer_not_to_say")
    seletor = f"#{radio_id}"
    if not engine.exists(seletor):
        msg = f"[CAMPO-NAO-ENCONTRADO] {chave} | valor='{valor}' | obrigatorio=True"
        _emitir_campo(engine, chave, "nao-encontrado")
        logger.error(msg)
        raise CampoNaoEncontradoError(msg)
    try:
        engine.check(seletor)
        _log_campo(chave, "ok", f"seletor={seletor}")
        _emitir_campo(engine, chave, "ok", seletor=seletor)
    except Exception as e:
        msg = f"[ERRO-CAMPO] {chave} | seletor={seletor} | erro={e}"
        _emitir_campo(engine, chave, "erro", seletor=seletor)
        logger.error(msg)
        raise


def _marcar_pcd(engine: BrowserEngine, dados: dict):
    """Marca os checkboxes de PcD informados (campo opcional)."""
    chave = "disabilities"
    pcd = obter(dados, "disabilities", []) or []
    if not pcd:
        _log_campo(chave, "ignorado-valor-vazio")
        _emitir_campo(engine, chave, "ignorado-valor-vazio")
        return
    for item in pcd:
        checkbox_id = _PCD.get(str(item).strip().lower())
        if checkbox_id is None:
            logger.warning(f"[CAMPO] pcd | status=valor-desconhecido | valor='{item}'")
            continue
        seletor = f"#{checkbox_id}"
        if not engine.exists(seletor):
            _log_campo(f"pcd-{checkbox_id}", "nao-encontrado")
            _emitir_campo(engine, chave, "nao-encontrado", seletor=seletor)
            continue
        try:
            engine.check(seletor)
            _log_campo(f"pcd-{checkbox_id}", "ok")
            _emitir_campo(engine, chave, "ok", seletor=seletor)
        except Exception as e:
            logger.warning(f"[CAMPO] pcd-{checkbox_id} | status=erro | erro={e}")
            _emitir_campo(engine, chave, "erro", seletor=seletor)


def _preencher_telefone(engine: BrowserEngine, valor: str):
    """Preenche o número de telefone (DDI default +55, campo com máscara)."""
    chave = "phone"
    if not valor:
        _log_campo(chave, "ignorado-valor-vazio")
        _emitir_campo(engine, chave, "ignorado-valor-vazio")
        return
    seletor = _resolver_campo(engine, chave)
    if seletor is None:
        msg = f"[CAMPO-NAO-ENCONTRADO] {chave} | valor='{valor}' | obrigatorio=True"
        _emitir_campo(engine, chave, "nao-encontrado")
        logger.error(msg)
        raise CampoNaoEncontradoError(msg)
    try:
        engine.click(seletor)
        time.sleep(0.3)
        engine.fill_field(seletor, "")
        time.sleep(0.2)
        # Campo com máscara (00 00000-0000): digitar tecla a tecla
        engine.type_text(seletor, _so_digitos(valor))
        _log_campo(chave, "ok", f"seletor={seletor}")
        _emitir_campo(engine, chave, "ok", seletor=seletor)
    except Exception as e:
        msg = f"[ERRO-CAMPO] {chave} | seletor={seletor} | erro={e}"
        _emitir_campo(engine, chave, "erro", seletor=seletor)
        if valor:
            logger.error(msg)
            raise


def _selecionar_pais(engine: BrowserEngine, valor: str = "BR"):
    """Seleciona o país no <select> nativo (campo opcional)."""
    chave = "country"
    seletor = _resolver_campo(engine, chave)
    if seletor is None:
        _log_campo(chave, "nao-encontrado")
        _emitir_campo(engine, chave, "nao-encontrado")
        return
    try:
        engine.select_option(seletor, valor)
        _log_campo(chave, "ok", f"valor='{valor}'")
        _emitir_campo(engine, chave, "ok", seletor=seletor)
    except Exception as e:
        logger.warning(f"[CAMPO] {chave} | status=erro | erro={e}")
        _emitir_campo(engine, chave, "erro", seletor=seletor)


def _preencher_endereco(engine: BrowserEngine, dados: dict):
    """Preenche a seção Endereço (todos os campos são opcionais no template)."""
    cidade = str(obter(dados, "city", "")).strip()
    estado = str(obter(dados, "state", "")).strip()

    # Compatibilidade com o formato do inhire "Cidade - UF"
    if not estado and " - " in cidade:
        partes = cidade.split(" - ")
        cidade, estado = partes[0].strip(), partes[-1].strip()

    _selecionar_pais(engine, str(obter(dados, "country", "BR")).upper())
    _preencher_campo(engine, "state", estado)
    _preencher_campo(engine, "city", cidade)
    _preencher_campo(engine, "neighborhood", obter(dados, "neighborhood", ""))
    _preencher_campo(engine, "address", obter(dados, "address", ""))
    _preencher_campo(engine, "zip_code", obter(dados, "zip_code", ""))


def _anexar_curriculo(engine: BrowserEngine, caminho: str):
    seletor = _resolver_campo(engine, "resume")
    if seletor is None:
        msg = f"[CAMPO-NAO-ENCONTRADO] resume | caminho='{caminho}' | obrigatorio=True"
        _emitir_campo(engine, "resume", "nao-encontrado")
        logger.error(msg)
        raise CampoNaoEncontradoError(msg)
    try:
        engine.force_upload(seletor, caminho)
        _log_campo("resume", "ok")
        _emitir_campo(engine, "resume", "ok", seletor=seletor)
    except Exception as e:
        msg = f"[ERRO-CAMPO] resume | seletor={seletor} | erro={e}"
        _emitir_campo(engine, "resume", "erro", seletor=seletor)
        logger.error(msg)
        raise


def _marcar_consentimento(engine: BrowserEngine):
    """Marca o checkbox de consentimento LGPD (obrigatório, required HTML)."""
    chave = "consent"
    seletor = _resolver_campo(engine, chave)
    if seletor is None:
        msg = f"[CAMPO-NAO-ENCONTRADO] {chave} | obrigatorio=True"
        _emitir_campo(engine, chave, "nao-encontrado")
        logger.error(msg)
        raise CampoNaoEncontradoError(msg)
    try:
        engine.check(seletor)
        _log_campo(chave, "ok")
        _emitir_campo(engine, chave, "ok", seletor=seletor)
    except Exception as e:
        # Checkbox oculto de verdade: clicar via JS marca mesmo assim
        try:
            engine.evaluate(f"document.querySelector('{seletor}')?.click()")
            _log_campo(chave, "ok-js")
            _emitir_campo(engine, chave, "ok-js", seletor=seletor)
        except Exception as e2:
            msg = f"[ERRO-CAMPO] {chave} | seletor={seletor} | erro={e} | fallback-js={e2}"
            _emitir_campo(engine, chave, "erro", seletor=seletor)
            logger.error(msg)
            raise


def _notificar_sucesso(engine: BrowserEngine):
    """Dispara alerta de sucesso sem enviar a candidatura (modo debug)."""
    # Handler vazio mantém o alert aberto até o navegador fechar
    engine.page.on("dialog", lambda dialog: None)
    engine.evaluate("setTimeout(() => alert('Vaga preenchida com sucesso! Confira.'), 0)")


def _submeter(engine: BrowserEngine):
    """Envia a candidatura clicando em 'Finalizar'.

    Em modo debug, apenas notifica sem enviar (alerta de sucesso).
    """
    if engine.debug:
        logger.info("[FLUXO] submit | status=debug-nao-enviado (alerta de sucesso exibido)")
        engine.emitir(STATUS_PROCESSING, "submit", status_campo="debug-nao-enviado")
        _notificar_sucesso(engine)
        return

    for sel in _SELETORES_SUBMIT:
        if not engine.exists(sel):
            continue
        engine.click(sel)
        logger.info(f"[FLUXO] submit | status=ok | seletor={sel}")
        engine.emitir(STATUS_PROCESSING, "submit", status_campo="ok", seletor=sel)
        return

    raise SubmitBloqueadoError(
        "[SUBMIT-NAO-ENCONTRADO] Botão de submit ('Finalizar') não encontrado no formulário."
    )


def _relatar_campos_faltantes(engine: BrowserEngine):
    """Loga campos visíveis não preenchidos (formato parseável por IA)."""
    faltantes = engine.relatorio_campos_nao_preenchidos()
    if not faltantes:
        logger.info("[RELATORIO] Todos os campos visíveis estão preenchidos.")
        return
    logger.warning(f"[RELATORIO] {len(faltantes)} campo(s) visível(is) não preenchido(s):")
    for c in faltantes:
        tipo = "OBRIGATORIO" if c["required"] else "opcional"
        logger.warning(
            f"[CAMPO-NAO-PREENCHIDO] {tipo} | label='{c['label']}' | "
            f"name='{c['name']}' | id='{c['id']}' | tag={c['tag']} type={c['type']}"
        )


@register_site("quickin", campos=_CAMPOS_USADOS)
def apply_quickin(engine: BrowserEngine, url_vaga: str, dados: dict, curriculo_path: str) -> bool:
    """Implementação da automação Quickin (jobs.quickin.io)."""
    logger.info(f"[FLUXO] site=quickin | url={url_vaga}")
    dados = normalizar(dados)
    engine.navigate(url_vaga)
    engine.emitir(STATUS_PROCESSING, "navegacao", status_campo="ok")

    _abrir_formulario(engine)

    # Dados básicos
    _preencher_campo(engine, "full_name", _exigir_nome_completo(dados), obrigatorio=True)
    cargo = obter(dados, "desired_role") or obter(dados, "headline") or ""
    _preencher_campo(engine, "desired_role", cargo)
    _selecionar_data_nascimento(engine, dados)
    _marcar_pcd(engine, dados)
    _selecionar_genero(engine, dados)

    # Contato
    _preencher_campo(engine, "email", obter(dados, "email", ""), obrigatorio=True)
    _preencher_telefone(engine, obter(dados, "phone", ""))

    # Endereço (opcional)
    _preencher_endereco(engine, dados)

    # Resumo das qualificações (opcional)
    _preencher_campo(engine, "summary", obter(dados, "summary", ""))

    # Currículo (obrigatório) + consentimento LGPD (obrigatório)
    if curriculo_path:
        _anexar_curriculo(engine, curriculo_path)
    _marcar_consentimento(engine)

    try:
        _submeter(engine)
    finally:
        _relatar_campos_faltantes(engine)

    logger.info("[FLUXO] site=quickin | status=concluido")
    return True
