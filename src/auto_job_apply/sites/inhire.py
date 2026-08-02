import logging
import time

from ..engine import BrowserEngine
from ..registry import register_site

logger = logging.getLogger(__name__)

# Alternativas de seletor para o botão de submit
_SELETORES_SUBMIT = [
    "button[type='submit']:has-text('Continuar inscri')",
    "button[type='submit']:has-text('Continuar')",
    "button:has-text('Continuar inscri')",
    "button[type='submit']",
]

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


def _so_digitos(valor) -> str:
    """Remove tudo que não for dígito."""
    return "".join(c for c in str(valor) if c.isdigit())


def _exigir_nome_completo(dados: dict) -> str:
    """Valida que o candidato informou nome e sobrenome."""
    nome = str(dados.get("nome", "")).strip()
    if len(nome.split()) < 2:
        raise ValueError("Campo 'nome' deve conter nome e sobrenome (ex.: 'Maria Silva').")
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


def _preencher_campo(engine: BrowserEngine, chave: str, valor: str, obrigatorio: bool = False):
    """Preenche um campo de texto com fallback de seletores e log estruturado."""
    if not valor:
        _log_campo(chave, "ignorado-valor-vazio")
        return
    seletor = _resolver_campo(engine, chave)
    if seletor is None:
        msg = f"[CAMPO-NAO-ENCONTRADO] {chave} | valor='{valor}' | obrigatorio={obrigatorio}"
        if obrigatorio:
            logger.error(msg)
            raise CampoNaoEncontradoError(msg)
        logger.warning(msg)
        return
    try:
        engine.fill_field(seletor, valor)
        _log_campo(chave, "ok", f"seletor={seletor}")
    except Exception as e:
        msg = f"[ERRO-CAMPO] {chave} | seletor={seletor} | erro={e}"
        if obrigatorio:
            logger.error(msg)
            raise
        logger.warning(msg)


def _selecionar_pais(engine: BrowserEngine):
    seletor = _resolver_campo(engine, "pais")
    if seletor is None:
        logger.warning("[CAMPO] pais | status=nao-encontrado")
        return
    try:
        engine.click(seletor)
        time.sleep(0.4)
        engine.click("[data-option-value='BR']", force=True)
        time.sleep(1)
        _log_campo("pais", "ok")
    except Exception as e:
        logger.warning(f"[CAMPO] pais | status=erro | erro={e}")


def _selecionar_cidade(engine: BrowserEngine, cidade_alvo: str):
    # O campo de cidade só aparece após selecionar o país (DOM dinâmico): aguardar
    gatilho = None
    for _ in range(5):
        gatilho = _resolver_campo(engine, "cidade")
        if gatilho:
            break
        time.sleep(1)
    busca = _resolver_campo(engine, "cidade_busca")
    primeira = _resolver_campo(engine, "cidade_primeira_opcao")
    if gatilho is None or busca is None or primeira is None:
        logger.warning("[CAMPO] cidade | status=nao-encontrado")
        return
    try:
        engine.click(gatilho)
        time.sleep(0.3)
        engine.fill_field(busca, cidade_alvo)
        time.sleep(0.5)
        # Clica na primeira opção (texto pode ter acentos)
        engine.click(primeira, force=True)
        _log_campo("cidade", "ok", f"valor='{cidade_alvo}'")
    except Exception as e:
        logger.warning(f"[CAMPO] cidade | status=erro | erro={e}")


def _preencher_pretensao_salarial(engine: BrowserEngine, valor: str):
    seletor = _resolver_campo(engine, "pretensao")
    if seletor is None:
        logger.warning("[CAMPO] pretensao-salarial | status=nao-encontrado")
        return
    try:
        engine.click(seletor)
        time.sleep(0.3)
        engine.fill_field(seletor, "")
        time.sleep(0.2)
        # Campo com máscara monetária: digitar tecla a tecla
        engine.type_text(seletor, valor)
        _log_campo("pretensao-salarial", "ok")
    except Exception as e:
        logger.warning(f"[CAMPO] pretensao-salarial | status=erro | erro={e}")


def _selecionar_disponibilidade(engine: BrowserEngine, valor: str):
    """Seleciona o radio 'Disponibilidade para trabalho presencial' (workModel).

    O input é estilizado e um <span> intercepta o clique: usa force=True.
    Campo obrigatório — falha explícita se não for encontrado/preenchido.
    """
    chave = "workmodel_sim" if valor == "Sim" else "workmodel_nao"
    seletor = _resolver_campo(engine, chave)
    if seletor is None:
        msg = (
            f"[CAMPO-NAO-ENCONTRADO] disponibilidade-presencial | "
            f"valor='{valor}' | obrigatorio=True"
        )
        logger.error(msg)
        raise CampoNaoEncontradoError(msg)
    try:
        engine.click(seletor, force=True)
        _log_campo("disponibilidade-presencial", "ok", f"seletor={seletor}")
    except Exception as e:
        msg = f"[ERRO-CAMPO] disponibilidade-presencial | seletor={seletor} | erro={e}"
        logger.error(msg)
        raise


def _selecionar_indicacao(engine: BrowserEngine):
    seletor = _resolver_campo(engine, "indicacao_nao")
    if seletor is None:
        _log_campo("indicacao-nao", "nao-encontrado")
        return
    try:
        engine.click(seletor, force=True)
        _log_campo("indicacao-nao", "ok")
    except Exception as e:
        logger.warning(f"[CAMPO] indicacao-nao | status=erro | erro={e}")


def _anexar_curriculo(engine: BrowserEngine, caminho: str):
    seletor = _resolver_campo(engine, "curriculo")
    if seletor is None:
        logger.warning("[CAMPO] curriculo | status=nao-encontrado")
        return
    try:
        engine.force_upload(seletor, caminho)
        _log_campo("curriculo", "ok")
    except Exception as e:
        logger.warning(f"[CAMPO] curriculo | status=erro | erro={e}")


def _avancar(engine: BrowserEngine):
    """Avança para a próxima aba; força via JS se o botão estiver desabilitado."""
    try:
        engine.click("button:has-text('Avançar')", attempts=2)
        _log_campo("avancar", "ok")
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
    finally:
        time.sleep(2)


def _marcar_privacidade(engine: BrowserEngine):
    seletor = _resolver_campo(engine, "privacidade")
    if seletor is None:
        _log_campo("privacidade", "nao-encontrado")
        return
    try:
        engine.check(seletor)
        _log_campo("privacidade", "ok")
    except Exception as e:
        # Checkbox oculto de verdade: clicar via JS marca mesmo assim
        try:
            engine.evaluate(f"document.querySelector('{seletor}')?.click()")
            _log_campo("privacidade", "ok-js")
        except Exception as e2:
            logger.warning(f"[CAMPO] privacidade | status=erro | erro={e} | fallback-js={e2}")


def _submeter(engine: BrowserEngine):
    """Envia a candidatura. Em modo debug, apenas notifica sem enviar."""
    if engine.debug:
        logger.info("[FLUXO] submit | status=debug-nao-enviado (alerta de sucesso exibido)")
        _notificar_sucesso(engine)
        return
    for sel in _SELETORES_SUBMIT:
        try:
            engine.click(sel)
            logger.info(f"[FLUXO] submit | status=ok | seletor={sel}")
            return
        except Exception:
            logger.warning(f"[FLUXO] submit | seletor={sel} | status=falhou")
    logger.warning("[FLUXO] submit | status=erro; tentando via JavaScript...")
    engine.evaluate(
        "document.querySelector('button[type=\"submit\"]')?.removeAttribute('disabled');"
        "document.querySelector('button[type=\"submit\"]')?.click();"
    )


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
        return
    try:
        engine.click(trigger_sel, force=True)
        time.sleep(0.4)
        engine.click(f"button[aria-label='{texto_opcao}']", force=True)
        time.sleep(0.3)
        _log_campo(label, "ok", f"opcao='{texto_opcao}'")
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
        except Exception as e2:
            logger.warning(f"[CAMPO] {label} | status=erro | erro={e} | fallback-js={e2}")


def marcar_checkbox_por_texto(engine: BrowserEngine, texto: str, label: str = "checkbox"):
    """Marca checkbox cujo label contenha o texto exato."""
    selector = f"label:has-text('{texto}') input[type='checkbox']"
    if not engine.exists(selector):
        _log_campo(label, "nao-encontrado")
        return
    try:
        engine.check(selector)
        _log_campo(label, "ok", f"texto='{texto}'")
    except Exception as e:
        logger.warning(f"[CAMPO] {label} | status=erro | erro={e}")


@register_site("inhire")
def apply_inhire(engine: BrowserEngine, url_vaga: str, dados: dict, curriculo_path: str) -> bool:
    """Implementação da automação inHire."""
    logger.info(f"[FLUXO] site=inhire | url={url_vaga}")
    engine.navigate(url_vaga)

    # Nome completo é obrigatório
    nome = _exigir_nome_completo(dados)
    _preencher_campo(engine, "nome", nome, obrigatorio=True)

    _preencher_campo(engine, "cpf", _so_digitos(dados.get("cpf", "")))
    _preencher_campo(engine, "email", dados.get("email", ""))
    _preencher_campo(engine, "telefone", _so_digitos(dados.get("telefone", "")))
    _preencher_campo(engine, "linkedin", dados.get("linkedin", ""))

    _selecionar_pais(engine)
    _selecionar_cidade(engine, dados.get("cidade", "Sao Jose - SC"))

    _selecionar_disponibilidade(engine, dados.get("disponibilidade_presencial", "Sim"))

    pretensao = _so_digitos(dados.get("pretensao_salarial", ""))
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
            engine, "questionsDiversity.genderIdentity", "Prefiro não responder", label="genero"
        )
        selecionar_react_dropdown(
            engine,
            "questionsDiversity.sexualOrientation",
            "Prefiro não responder",
            label="orientacao",
        )
        selecionar_react_dropdown(
            engine, "questionsDiversity.colourAndEthnicity", "Prefiro não responder", label="raca"
        )
        selecionar_react_dropdown(
            engine, "questionsDiversity.peopleWithDisability", "Não", label="pcd"
        )

        _marcar_privacidade(engine)
        time.sleep(0.5)

        _submeter(engine)
    finally:
        _relatar_campos_faltantes(engine)

    logger.info("[FLUXO] site=inhire | status=concluido")
    return True
