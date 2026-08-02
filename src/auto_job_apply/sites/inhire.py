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


def _so_digitos(valor) -> str:
    """Remove tudo que não for dígito."""
    return "".join(c for c in str(valor) if c.isdigit())


def _exigir_nome_completo(dados: dict) -> str:
    """Valida que o candidato informou nome e sobrenome."""
    nome = str(dados.get("nome", "")).strip()
    if len(nome.split()) < 2:
        raise ValueError("Campo 'nome' deve conter nome e sobrenome (ex.: 'Maria Silva').")
    return nome


def _opcional(func, label=""):
    """Executa ação opcional: se falhar, loga e segue (campos são opcionais)."""
    try:
        func()
        logger.info(f"[{label}] ok")
    except Exception as e:
        logger.warning(f"[{label}] ignorado: {e}")


def _selecionar_pais(engine: BrowserEngine):
    engine.click("#country")
    time.sleep(0.4)
    engine.click("[data-option-value='BR']")
    time.sleep(1)


def _selecionar_cidade(engine: BrowserEngine, cidade_alvo: str):
    engine.click("#districtBr")
    time.sleep(0.3)
    engine.fill_field("div[data-component-name='DropdownOptionsSearch'] input", cidade_alvo)
    time.sleep(0.3)
    opcao_exata = f"button[data-component-name='DropdownOption'][data-option-value='{cidade_alvo}']"
    try:
        engine.click(opcao_exata)
    except Exception:
        # Tenta a primeira opção da lista de resultados
        engine.click(
            "div[data-component-name='DropdownOptionsList'] "
            "button[data-component-name='DropdownOption']"
        )


def _preencher_pretensao_salarial(engine: BrowserEngine, valor: str):
    engine.click("input[name='salaryExpectation']")
    time.sleep(0.3)
    engine.fill_field("input[name='salaryExpectation']", "")
    time.sleep(0.2)
    # Campo com máscara monetária: digitar tecla a tecla
    engine.type_text("input[name='salaryExpectation']", valor)


def _selecionar_disponibilidade(engine: BrowserEngine, valor: str):
    """Seleciona o radio 'Disponibilidade para trabalho presencial' (workModel)."""
    radio_value = "true" if valor == "Sim" else "false"
    engine.click(f"input[name='workModel'][value='{radio_value}']")


def _avancar(engine: BrowserEngine):
    """Avança para a próxima aba; força via JS se o botão estiver desabilitado."""
    try:
        engine.click("button:has-text('Avançar')")
    except Exception:
        logger.warning("'Avançar' não habilitado; forçando via JS...")
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
    time.sleep(2)


def _notificar_sucesso(engine: BrowserEngine):
    """Dispara alerta de sucesso sem enviar a candidatura (modo debug)."""
    # Handler vazio mantém o alert aberto até o navegador fechar
    engine.page.on("dialog", lambda dialog: None)
    engine.evaluate("setTimeout(() => alert('Vaga preenchida com sucesso! Confira.'), 0)")


def _submeter(engine: BrowserEngine):
    """Envia a candidatura. Em modo debug, apenas notifica sem enviar."""
    if engine.debug:
        logger.info("Modo debug ativado: candidatura NÃO será enviada.")
        _notificar_sucesso(engine)
        return
    for sel in _SELETORES_SUBMIT:
        try:
            engine.click(sel)
            logger.info(f"Formulário submetido via '{sel}'!")
            return
        except Exception:
            logger.warning(f"Submit via '{sel}' falhou; tentando próximo...")
    # Último recurso: submit via JS
    logger.warning("Tentando submit via JavaScript...")
    engine.evaluate(
        "document.querySelector('button[type=\"submit\"]')?.removeAttribute('disabled');"
        "document.querySelector('button[type=\"submit\"]')?.click();"
    )


def selecionar_react_dropdown(
    engine: BrowserEngine, dropdown_id: str, texto_opcao: str, label: str = "dropdown"
):
    """Seleciona opção em dropdown React (react-dropdown-select)."""
    css_id = dropdown_id.replace(".", "\\.")
    engine.click(f"#{css_id} .react-dropdown-select")
    time.sleep(0.4)
    engine.click(f"button[aria-label='{texto_opcao}']")
    time.sleep(0.3)
    logger.info(f"[{label}] Opção '{texto_opcao}' selecionada.")


def marcar_checkbox_por_texto(engine: BrowserEngine, texto: str, label: str = "checkbox"):
    """Marca checkbox cujo label contenha o texto exato."""
    engine.click(f"label:has-text('{texto}') input[type='checkbox']")
    logger.info(f"[{label}] Checkbox '{texto}' marcado.")


@register_site("inhire")
def apply_inhire(engine: BrowserEngine, url_vaga: str, dados: dict, curriculo_path: str) -> bool:
    """Implementação da automação inHire."""
    logger.info(f"Navegando para: {url_vaga}")
    engine.navigate(url_vaga)

    # Nome completo é obrigatório
    nome = _exigir_nome_completo(dados)
    engine.fill_field("input[name='name']", nome)

    _opcional(
        lambda: engine.fill_field(
            "input[name='document.value']", _so_digitos(dados.get("cpf", ""))
        ),
        label="cpf",
    )
    _opcional(
        lambda: engine.fill_field("input[name='email']", dados.get("email", "")), label="email"
    )
    _opcional(
        lambda: engine.fill_field("input[name='phone']", _so_digitos(dados.get("telefone", ""))),
        label="telefone",
    )
    _opcional(
        lambda: engine.fill_field("input[name='linkedinUsername']", dados.get("linkedin", "")),
        label="linkedin",
    )

    _opcional(lambda: _selecionar_pais(engine), label="pais")
    _opcional(
        lambda: _selecionar_cidade(engine, dados.get("cidade", "Sao Jose - SC")), label="cidade"
    )

    _opcional(
        lambda: _selecionar_disponibilidade(engine, dados.get("disponibilidade_presencial", "Sim")),
        label="disponibilidade-presencial",
    )

    pretensao = _so_digitos(dados.get("pretensao_salarial", ""))
    if pretensao:
        _opcional(
            lambda: _preencher_pretensao_salarial(engine, pretensao), label="pretensao-salarial"
        )

    _opcional(
        lambda: engine.click("input[name='isIndication'][value='false']"), label="indicacao-nao"
    )

    if curriculo_path:
        _opcional(
            lambda: engine.force_upload("input[type='file'][name='resume']", curriculo_path),
            label="curriculo",
        )

    _avancar(engine)

    # Aba diversidade — tudo opcional, "Prefiro não responder" por padrão
    _opcional(
        lambda: marcar_checkbox_por_texto(engine, "Prefiro não responder"), label="diversityGroup"
    )
    _opcional(
        lambda: selecionar_react_dropdown(
            engine, "questionsDiversity.genderIdentity", "Prefiro não responder"
        ),
        label="genero",
    )
    _opcional(
        lambda: selecionar_react_dropdown(
            engine, "questionsDiversity.sexualOrientation", "Prefiro não responder"
        ),
        label="orientacao",
    )
    _opcional(
        lambda: selecionar_react_dropdown(
            engine, "questionsDiversity.colourAndEthnicity", "Prefiro não responder"
        ),
        label="raca",
    )
    _opcional(
        lambda: selecionar_react_dropdown(engine, "questionsDiversity.peopleWithDisability", "Não"),
        label="pcd",
    )

    _opcional(lambda: engine.click("#privacyPolicy"), label="privacidade")
    time.sleep(0.5)

    _submeter(engine)
    logger.info("Candidatura inHire processada.")
    return True
