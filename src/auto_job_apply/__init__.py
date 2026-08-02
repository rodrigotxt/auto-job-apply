from .engine import BrowserEngine
from .registry import SITES_REGISTRY

# Importar módulos de sites para garantir que o registro ocorra
from .sites import gupy, inhire


def apply(
    site: str,
    url_vaga: str,
    dados: dict,
    curriculo_path: str,
    debug: bool = False,
    delay: float = 0.0,
) -> bool:
    """Interface unificada para automação de candidaturas.

    Args:
        site: nome do site registrado (ex: 'inhire', 'gupy').
        url_vaga: URL da vaga.
        dados: dict com os dados do candidato.
        curriculo_path: caminho do arquivo de currículo (PDF).
        debug: se True, mantém o navegador visível e aberto ao final (15s).
        delay: pausa em segundos após cada interação com o formulário.
    """
    if site not in SITES_REGISTRY:
        raise ValueError(f"Site '{site}' não registrado no sistema.")

    engine = BrowserEngine(headless=not debug, debug=debug, delay=delay)
    try:
        return SITES_REGISTRY[site](engine, url_vaga, dados, curriculo_path)
    finally:
        engine.wait_before_close()
        engine.close()
