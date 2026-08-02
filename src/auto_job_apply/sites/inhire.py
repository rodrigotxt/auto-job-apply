import logging
import time

from ..engine import BrowserEngine
from ..registry import register_site

logger = logging.getLogger(__name__)


def _safe_action(action_func, *args, **kwargs):
    """Executa uma ação de forma segura, ignorando erros comuns."""
    try:
        return action_func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Ação falhou: {e}")
        return False


def selecionar_react_dropdown(
    engine: BrowserEngine, dropdown_id: str, texto_opcao: str, label: str = "dropdown"
):
    """Seleciona opção em dropdown React."""
    try:
        css_id = dropdown_id.replace(".", "\\.")
        trigger_sel = f"#{css_id} .react-dropdown-select"
        engine.click(trigger_sel)
        time.sleep(0.4)

        opcao_sel = f"button[aria-label='{texto_opcao}']"
        engine.click(opcao_sel)
        time.sleep(0.3)
        logger.info(f"[{label}] Opção '{texto_opcao}' selecionada.")
        return True
    except Exception as e:
        logger.warning(f"[{label}] Erro no dropdown: {e}")
        return False


def marcar_checkbox_por_texto(engine: BrowserEngine, texto: str, label: str = "checkbox"):
    """Marca checkbox via label."""
    try:
        selector = f"label:has-text('{texto}') input[type='checkbox']"
        # O force=True é tratado internamente pela engine se necessário,
        # mas aqui usamos o click do playwright via engine
        engine.click(selector)
        logger.info(f"[{label}] Checkbox '{texto}' marcado.")
        return True
    except Exception as e:
        logger.warning(f"[{label}] Erro checkbox '{texto}': {e}")
        return False


@register_site("inhire")
def apply_inhire(engine: BrowserEngine, url_vaga: str, dados: dict, curriculo_path: str) -> bool:
    """Implementação da automação inHire utilizando BrowserEngine."""
    logger.info(f"Navegando para: {url_vaga}")
    engine.navigate(url_vaga)

    # Preenchimento de dados pessoais
    if nome := dados.get("nome"):
        engine.fill_field("input[name='name']", nome)

    if email := dados.get("email"):
        engine.fill_field("input[name='email']", email)

    if tel := dados.get("telefone"):
        # Limpeza simples
        tel_digits = "".join(c for c in str(tel) if c.isdigit())
        engine.fill_field("input[name='phone']", tel_digits)

    # Upload de currículo
    if curriculo_path:
        engine.force_upload("input[type='file'][name='resume']", curriculo_path)

    # Avançar
    engine.click("button:has-text('Avançar')")
    time.sleep(1)

    # Diversidade (exemplo)
    marcar_checkbox_por_texto(engine, "Prefiro não responder", label="diversityGroup")

    logger.info("Candidatura inHire processada.")
    return True
