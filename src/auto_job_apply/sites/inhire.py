import logging
import time

from ..engine import BrowserEngine
from ..progresso import STATUS_PROCESSING
from ..registry import register_site
from ..schema import normalizar, obter

logger = logging.getLogger(__name__)

# Alternativas de seletor para o botão de submit
_SELETORES_SUBMIT = [
    "button[type='submit']:has-text('Continuar inscri')",
    "button[type='submit']:has-text('Continuar')",
    "button:has-text('Continuar inscri')",
    "button[type='submit']",
]

# Tempo máximo esperando o botão de submit habilitar (validação assíncrona)
_TIMEOUT_SUBMIT = 10.0

# Seletores candidatos por campo (fallback em ordem de preferência)
_CAMPOS = {
    "nome": ["input[name='name']", "input#name"],
    "cpf": ["input[name='document.value']", "input[name*='document']"],
    "email": ["input[name='email']", "input[type='email']"],
    "telefone": ["input[name='phone']", "input[type='tel']"],
    "linkedin": ["input[name='linkedinUsername']"],
    "workmodel_sim": ["input[name='workModel'][value='true']"],
    "workmodel_nao": ["input[name='workModel'][value='false']"],
    "indicacao_nao": ["input[name='isIndication'][value='false']"],
    "curriculo": ["input[type='file'][name='resume']", "input[type='file']"],
    "pais": ["#country"],
    "cidade": ["#districtBr", "input[name='districtBr']", "input[name='district']", "#district"],
    "cidade_busca": ["div[data-component-name='DropdownOptionsSearch'] input"],
    "cidade_primeira_opcao": [
        "div[data-component-name='DropdownOptionsList'] "
        "button[data-component-name='DropdownOption']"
    ],
    "pretensao": ["input[name='salaryExpectation']"],
    "privacidade": ["#privacyPolicy"],
}

# Palavras-chave para busca fuzzy por label (último recurso)
_LABELS = {
    "nome": ["nome completo", "nome"],
    "email": ["e-mail", "email"],
    "telefone": ["telefone", "celular", "phone"],
    "cpf": ["cpf"],
    "linkedin": ["linkedin"],
}


class CampoNaoEncontradoError(ValueError):
    """Campo obrigatório não encontrado no formulário."""


class SubmitBloqueadoError(RuntimeError):
    """Botão de submit não habilitou ao final do fluxo (campo obrigatório pendente)."""


# Campos de dados_candidatura (schema.py) usados por este site.
_CAMPOS_USADOS = [
    "full_name",
    "cpf",
    "email",
    "phone",
    "linkedin_url",
    "country",
    "city",
    "work_model",
    "contract_type",
    "salary_expectation",
    "referral",
    "gender_identity",
    "sexual_orientation",
    "race_ethnicity",
    "disability_identity",
    "consent",
]


def _so_digitos(valor) -> str:
    """Remove tudo que não for dígito."""
    return "".join(c for c in str(valor) if c.isdigit())


def _exigir_nome_completo(dados: dict) -> str:
    """Valida que o candidato informou nome e sobrenome."""
    nome = str(obter(dados, "full_name", "")).strip()
    if len(nome.split()) < 2:
        raise ValueError("Campo 'full_name' deve conter nome e sobrenome (ex.: 'Maria Silva').")
    return nome


def _resolver_campo(engine: BrowserEngine, chave: str) -> str | None:
    """Resolve o seletor do campo: candidatos conhecidos, depois fuzzy por label."""
    for sel in _CAMPOS.get(chave, []):
        if engine.exists(sel):
            return sel
    for palavra in _LABELS.get(chave, []):
        sel = engine.campo_por_label(palavra)
        if sel:
            logger.info(f"[CAMPO] {chave} | status=resolvido-por-label | seletor={sel}")
            return sel
    return None


def _log_campo(chave: str, status: str, detalhe: str = ""):
    logger.info(f"[CAMPO] {chave} | status={status} | {detalhe}".rstrip(" |"))


def _emitir_campo(engine: BrowserEngine, chave: str, status: str, seletor: str | None = None):
    """Emite evento de progresso de um campo (etapa='campo')."""
    engine.emitir(STATUS_PROCESSING, "campo", campo=chave, status_campo=status, seletor=seletor)


def _preencher_campo(engine: BrowserEngine, chave: str, valor: str, obrigatorio: bool = False):
    """Preenche um campo de texto com fallback de seletores e log estruturado."""
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


def _selecionar_pais(engine: BrowserEngine):
    seletor = _resolver_campo(engine, "pais")
    if seletor is None:
        logger.warning("[CAMPO] pais | status=nao-encontrado")
        _emitir_campo(engine, "pais", "nao-encontrado")
        return
    try:
        engine.click(seletor)
        time.sleep(0.4)
        engine.click("[data-option-value='BR']", force=True)
        time.sleep(1)
        _log_campo("pais", "ok")
        _emitir_campo(engine, "pais", "ok", seletor=seletor)
    except Exception as e:
        logger.warning(f"[CAMPO] pais | status=erro | erro={e}")
        _emitir_campo(engine, "pais", "erro", seletor=seletor)


def _selecionar_cidade(engine: BrowserEngine, cidade_alvo: str):
    # O campo de cidade só aparece após selecionar o país (DOM dinâmico)
    gatilho = None
    for _ in range(5):
        gatilho = _resolver_campo(engine, "cidade")
        if gatilho:
            break
        time.sleep(1)
    if gatilho is None:
        logger.warning("[CAMPO] cidade | status=nao-encontrado (gatilho)")
        _emitir_campo(engine, "cidade", "nao-encontrado")
        return
    try:
        engine.click(gatilho)
        time.sleep(0.3)
        # A busca e a lista só existem com o dropdown aberto (DOM dinâmico)
        busca = None
        for _ in range(5):
            busca = _resolver_campo(engine, "cidade_busca")
            if busca:
                break
            time.sleep(0.5)
        if busca is None:
            logger.warning("[CAMPO] cidade | status=erro | busca não apareceu")
            _emitir_campo(engine, "cidade", "erro", seletor=gatilho)
            return
        engine.fill_field(busca, cidade_alvo)
        time.sleep(0.5)
        primeira = _resolver_campo(engine, "cidade_primeira_opcao")
        if primeira is None:
            logger.warning("[CAMPO] cidade | status=erro | lista de opções não apareceu")
            _emitir_campo(engine, "cidade", "erro", seletor=gatilho)
            return
        engine.click(primeira, force=True)
        _log_campo("cidade", "ok", f"valor='{cidade_alvo}'")
        _emitir_campo(engine, "cidade", "ok", seletor=gatilho)
    except Exception as e:
        logger.warning(f"[CAMPO] cidade | status=erro | erro={e}")
        _emitir_campo(engine, "cidade", "erro", seletor=gatilho)


def _preencher_pretensao_salarial(engine: BrowserEngine, valor: str):
    seletor = _resolver_campo(engine, "pretensao")
    if seletor is None:
        logger.warning("[CAMPO] pretensao-salarial | status=nao-encontrado")
        _emitir_campo(engine, "pretensao-salarial", "nao-encontrado")
        return
    try:
        engine.click(seletor)
        time.sleep(0.3)
        engine.fill_field(seletor, "")
        time.sleep(0.2)
        # Campo com máscara monetária: digitar tecla a tecla
        engine.type_text(seletor, valor)
        _log_campo("pretensao-salarial", "ok")
        _emitir_campo(engine, "pretensao-salarial", "ok", seletor=seletor)
    except Exception as e:
        logger.warning(f"[CAMPO] pretensao-salarial | status=erro | erro={e}")
        _emitir_campo(engine, "pretensao-salarial", "erro", seletor=seletor)


def _mapear_work_model(valor: str) -> str:
    """Converte work_model (remote/hybrid/onsite, sim/não) para Sim/Não.

    O form inhire pergunta "Disponibilidade para trabalho presencial" com
    Sim/Não. Quem aceita presencial (ou híbrido) responde Sim; remoto
    estrito responde Não. Default: Sim (disponível para presencial).
    """
    v = str(valor).strip().lower()
    if v in ("nao", "não", "no", "false", "remote", "remoto"):
        return "Não"
    return "Sim"


def _texto_diversidade(
    dados: dict, chave: str, default_texto: str = "Prefiro não responder"
) -> str:
    """Resolve o texto da opção de diversidade no dropdown do form.

    Valores do schema (prefer_not_to_say, male, female, no, yes...) são
    convertidos para o texto exibido; qualquer outro valor é usado como o
    texto da opção diretamente.
    """
    valor = str(obter(dados, chave, "")).strip().lower()
    if not valor:
        return default_texto
    if valor in ("prefer_not_to_say", "prefiro não responder", "prefiro nao responder"):
        return "Prefiro não responder"
    if chave == "disability_identity":
        if valor in ("no", "não", "nao"):
            return "Não"
        if valor in ("yes", "sim"):
            return "Sim"
    return str(obter(dados, chave))


def _selecionar_disponibilidade(engine: BrowserEngine, valor: str):
    """Seleciona o radio 'Disponibilidade para trabalho presencial' (workModel).

    O input é estilizado e um <span> intercepta o clique: usa force=True.
    Nem toda vaga tem essa pergunta: após as tentativas, se o campo não
    existir (ou falhar), ignora e segue o fluxo (não aborta a candidatura).
    """
    chave = "workmodel_sim" if valor == "Sim" else "workmodel_nao"
    seletor = None
    for _ in range(engine.max_attempts):
        seletor = _resolver_campo(engine, chave)
        if seletor:
            break
        time.sleep(engine.retry_delay)
    if seletor is None:
        msg = (
            f"[CAMPO-NAO-ENCONTRADO] disponibilidade-presencial | "
            f"valor='{valor}' | obrigatorio=False | ignorado"
        )
        _emitir_campo(engine, "disponibilidade-presencial", "nao-encontrado")
        logger.warning(msg)
        return
    try:
        engine.click(seletor, force=True)
        _log_campo("disponibilidade-presencial", "ok", f"seletor={seletor}")
        _emitir_campo(engine, "disponibilidade-presencial", "ok", seletor=seletor)
    except Exception as e:
        msg = f"[ERRO-CAMPO] disponibilidade-presencial | seletor={seletor} | erro={e} | ignorado"
        _emitir_campo(engine, "disponibilidade-presencial", "erro", seletor=seletor)
        logger.warning(msg)


def _selecionar_tipo_contrato(engine: BrowserEngine, dados: dict):
    """Seleciona o radio 'Tipo de contrato' (input[name='contractType']), ex.: CLT.

    Valor vem de dados['contract_type'] (padrão do schema); default CLT.
    Só existe em algumas vagas: após as tentativas, se o campo não existir
    (ou falhar), ignora e segue o fluxo (não aborta a candidatura).
    """
    valor = str(obter(dados, "contract_type", "CLT") or "CLT")
    seletor = f"input[name='contractType'][value='{valor}']"
    encontrado = False
    for _ in range(engine.max_attempts):
        if engine.exists(seletor):
            encontrado = True
            break
        time.sleep(engine.retry_delay)
    if not encontrado:
        msg = (
            f"[CAMPO-NAO-ENCONTRADO] tipo-contrato | valor='{valor}' | "
            "obrigatorio=False | ignorado"
        )
        _emitir_campo(engine, "tipo-contrato", "nao-encontrado")
        logger.warning(msg)
        return
    try:
        engine.click(seletor, force=True)
        _log_campo("tipo-contrato", "ok", f"seletor={seletor}")
        _emitir_campo(engine, "tipo-contrato", "ok", seletor=seletor)
    except Exception as e:
        msg = f"[ERRO-CAMPO] tipo-contrato | seletor={seletor} | erro={e} | ignorado"
        _emitir_campo(engine, "tipo-contrato", "erro", seletor=seletor)
        logger.warning(msg)


def _selecionar_indicacao(engine: BrowserEngine):
    seletor = _resolver_campo(engine, "indicacao_nao")
    if seletor is None:
        _log_campo("indicacao-nao", "nao-encontrado")
        _emitir_campo(engine, "indicacao-nao", "nao-encontrado")
        return
    try:
        engine.click(seletor, force=True)
        _log_campo("indicacao-nao", "ok")
        _emitir_campo(engine, "indicacao-nao", "ok", seletor=seletor)
    except Exception as e:
        logger.warning(f"[CAMPO] indicacao-nao | status=erro | erro={e}")
        _emitir_campo(engine, "indicacao-nao", "erro", seletor=seletor)


def _anexar_curriculo(engine: BrowserEngine, caminho: str):
    seletor = _resolver_campo(engine, "curriculo")
    if seletor is None:
        logger.warning("[CAMPO] curriculo | status=nao-encontrado")
        _emitir_campo(engine, "curriculo", "nao-encontrado")
        return
    try:
        engine.force_upload(seletor, caminho)
        _log_campo("curriculo", "ok")
        _emitir_campo(engine, "curriculo", "ok", seletor=seletor)
    except Exception as e:
        logger.warning(f"[CAMPO] curriculo | status=erro | erro={e}")
        _emitir_campo(engine, "curriculo", "erro", seletor=seletor)


def _avancar(engine: BrowserEngine):
    """Avança para a próxima aba; força via JS se o botão estiver desabilitado."""
    try:
        engine.click("button:has-text('Avançar')", attempts=2)
        _log_campo("avancar", "ok")
        engine.emitir(STATUS_PROCESSING, "avancar", status_campo="ok")
        return
    except Exception:
        logger.warning("[FLUXO] avancar | botão desabilitado; forçando via JS...")
        # :has-text não é seletor CSS válido no browser — usar XPath
        engine.evaluate(
            """(() => {
              const btn = document.evaluate(
                "//button[contains(normalize-space(.), 'Avançar')]",
                document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
              ).singleNodeValue;
              if (btn) {
                btn.removeAttribute('disabled');
                btn.click();
                return 'ok';
              }
              return 'not found';
            })()"""
        )
        _log_campo("avancar", "forcado-js")
        engine.emitir(STATUS_PROCESSING, "avancar", status_campo="forcado-js")
    finally:
        time.sleep(2)


def _marcar_privacidade(engine: BrowserEngine):
    seletor = _resolver_campo(engine, "privacidade")
    if seletor is None:
        _log_campo("privacidade", "nao-encontrado")
        _emitir_campo(engine, "privacidade", "nao-encontrado")
        return
    try:
        engine.check(seletor)
        _log_campo("privacidade", "ok")
        _emitir_campo(engine, "privacidade", "ok", seletor=seletor)
    except Exception as e:
        # Checkbox oculto de verdade: clicar via JS marca mesmo assim
        try:
            engine.evaluate(f"document.querySelector('{seletor}')?.click()")
            _log_campo("privacidade", "ok-js")
            _emitir_campo(engine, "privacidade", "ok-js", seletor=seletor)
        except Exception as e2:
            logger.warning(f"[CAMPO] privacidade | status=erro | erro={e} | fallback-js={e2}")
            _emitir_campo(engine, "privacidade", "erro", seletor=seletor)


def _submeter(engine: BrowserEngine):
    """Envia a candidatura. Em modo debug, apenas notifica sem enviar.

    O botão precisa estar HABILITADO: aguarda até _TIMEOUT_SUBMIT pela
    validação assíncrona do formulário. Se continuar desabilitado ao final
    (ex.: campo obrigatório como contractType não preenchido), levanta
    SubmitBloqueadoError — NUNCA força o clique via JS em botão desabilitado.
    """
    if engine.debug:
        logger.info("[FLUXO] submit | status=debug-nao-enviado (alerta de sucesso exibido)")
        engine.emitir(STATUS_PROCESSING, "submit", status_campo="debug-nao-enviado")
        _notificar_sucesso(engine)
        return

    encontrado = False
    for sel in _SELETORES_SUBMIT:
        if not engine.exists(sel):
            continue
        encontrado = True
        if engine.wait_enabled(sel, timeout=_TIMEOUT_SUBMIT):
            engine.click(sel)
            logger.info(f"[FLUXO] submit | status=ok | seletor={sel}")
            engine.emitir(STATUS_PROCESSING, "submit", status_campo="ok", seletor=sel)
            return

    if not encontrado:
        raise SubmitBloqueadoError(
            "[SUBMIT-NAO-ENCONTRADO] Botão de submit não encontrado no formulário."
        )

    # Botão existe mas permaneceu desabilitado: relatório dos campos pendentes
    faltantes = engine.relatorio_campos_nao_preenchidos()
    detalhe = "; ".join(
        f"{c['name'] or c['id'] or c['label'] or '?'} (required={c['required']})"
        for c in faltantes
    ) or "nenhum campo vazio detectado (validação custom)"
    msg = (
        "[SUBMIT-BLOQUEADO] Botão de submit permaneceu desabilitado após o preenchimento. "
        f"Campos visíveis não preenchidos: {detalhe}"
    )
    logger.error(msg)
    engine.emitir(STATUS_PROCESSING, "submit", status_campo="bloqueado", detalhe=detalhe)
    raise SubmitBloqueadoError(msg)


def _notificar_sucesso(engine: BrowserEngine):
    """Dispara alerta de sucesso sem enviar a candidatura (modo debug)."""
    # Handler vazio mantém o alert aberto até o navegador fechar
    engine.page.on("dialog", lambda dialog: None)
    engine.evaluate("setTimeout(() => alert('Vaga preenchida com sucesso! Confira.'), 0)")


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


def selecionar_react_dropdown(
    engine: BrowserEngine, dropdown_id: str, texto_opcao: str, label: str = "dropdown"
):
    """Seleciona opção em dropdown React (react-dropdown-select)."""
    css_id = dropdown_id.replace(".", "\\.")
    trigger_sel = f"#{css_id} .react-dropdown-select"
    if not engine.exists(trigger_sel):
        _log_campo(label, "nao-encontrado")
        _emitir_campo(engine, label, "nao-encontrado")
        return
    try:
        engine.click(trigger_sel, force=True)
        time.sleep(0.4)
        engine.click(f"button[aria-label='{texto_opcao}']", force=True)
        time.sleep(0.3)
        _log_campo(label, "ok", f"opcao='{texto_opcao}'")
        _emitir_campo(engine, label, "ok", seletor=trigger_sel)
    except Exception as e:
        # Dropdown oculto/colapsado: tentar via JS
        try:
            engine.evaluate(f"document.querySelector('{trigger_sel}')?.click()")
            time.sleep(0.4)
            engine.evaluate(
                f"[...document.querySelectorAll('button')].find(b => "
                f"b.getAttribute('aria-label') === '{texto_opcao}')?.click()"
            )
            time.sleep(0.3)
            _log_campo(label, "ok-js", f"opcao='{texto_opcao}'")
            _emitir_campo(engine, label, "ok-js", seletor=trigger_sel)
        except Exception as e2:
            logger.warning(f"[CAMPO] {label} | status=erro | erro={e} | fallback-js={e2}")
            _emitir_campo(engine, label, "erro", seletor=trigger_sel)


def marcar_checkbox_por_texto(engine: BrowserEngine, texto: str, label: str = "checkbox"):
    """Marca checkbox cujo label contenha o texto exato."""
    selector = f"label:has-text('{texto}') input[type='checkbox']"
    if not engine.exists(selector):
        _log_campo(label, "nao-encontrado")
        _emitir_campo(engine, label, "nao-encontrado")
        return
    try:
        engine.check(selector)
        _log_campo(label, "ok", f"texto='{texto}'")
        _emitir_campo(engine, label, "ok", seletor=selector)
    except Exception as e:
        logger.warning(f"[CAMPO] {label} | status=erro | erro={e}")
        _emitir_campo(engine, label, "erro", seletor=selector)


@register_site("inhire", campos=_CAMPOS_USADOS)
def apply_inhire(engine: BrowserEngine, url_vaga: str, dados: dict, curriculo_path: str) -> bool:
    """Implementação da automação inHire."""
    logger.info(f"[FLUXO] site=inhire | url={url_vaga}")
    dados = normalizar(dados)
    engine.navigate(url_vaga)
    engine.emitir(STATUS_PROCESSING, "navegacao", status_campo="ok")

    # Nome completo é obrigatório
    nome = _exigir_nome_completo(dados)
    _preencher_campo(engine, "nome", nome, obrigatorio=True)

    _preencher_campo(engine, "cpf", _so_digitos(obter(dados, "cpf", "")))
    _preencher_campo(engine, "email", obter(dados, "email", ""))
    _preencher_campo(engine, "telefone", _so_digitos(obter(dados, "phone", "")))
    _preencher_campo(engine, "linkedin", obter(dados, "linkedin_url", ""))

    _selecionar_pais(engine)
    _selecionar_cidade(engine, obter(dados, "city", "Sao Jose - SC"))

    _selecionar_disponibilidade(engine, _mapear_work_model(obter(dados, "work_model", "Sim")))
    _selecionar_tipo_contrato(engine, dados)

    pretensao = _so_digitos(obter(dados, "salary_expectation", ""))
    if pretensao:
        _preencher_pretensao_salarial(engine, pretensao)

    _selecionar_indicacao(engine)

    if curriculo_path:
        _anexar_curriculo(engine, curriculo_path)

    try:
        _avancar(engine)

        # Aba diversidade — tudo opcional, "Prefiro não responder" por padrão
        marcar_checkbox_por_texto(engine, "Prefiro não responder", label="diversityGroup")
        selecionar_react_dropdown(
            engine,
            "questionsDiversity.genderIdentity",
            _texto_diversidade(dados, "gender_identity"),
            label="genero",
        )
        selecionar_react_dropdown(
            engine,
            "questionsDiversity.sexualOrientation",
            _texto_diversidade(dados, "sexual_orientation"),
            label="orientacao",
        )
        selecionar_react_dropdown(
            engine,
            "questionsDiversity.colourAndEthnicity",
            _texto_diversidade(dados, "race_ethnicity"),
            label="raca",
        )
        selecionar_react_dropdown(
            engine,
            "questionsDiversity.peopleWithDisability",
            _texto_diversidade(dados, "disability_identity", "Não"),
            label="pcd",
        )

        _marcar_privacidade(engine)
        time.sleep(0.5)

        _submeter(engine)
    finally:
        _relatar_campos_faltantes(engine)

    logger.info("[FLUXO] site=inhire | status=concluido")
    return True
