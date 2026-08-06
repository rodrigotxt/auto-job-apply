import logging
import time

from .engine import BrowserEngine
from .progresso import (
    STATUS_COMPLETED,
    STATUS_ERROR,
    STATUS_PROCESSING,
    capturar_log,
    emitir_seguro,
)
from .registry import SITES_REGISTRY
from .schema import normalizar

logger = logging.getLogger(__name__)

# Importar módulos de sites para garantir que o registro ocorra
from .sites import gupy, inhire, quickin  # noqa: E402,F401


def apply(
    site: str,
    url_vaga: str,
    dados: dict,
    curriculo_path: str,
    debug: bool = False,
    delay: float = 0.0,
    on_progress=None,
) -> dict:
    """Interface unificada para automação de candidaturas.

    Args:
        site: nome do site registrado (ex: 'inhire', 'gupy').
        url_vaga: URL da vaga.
        dados: dict com os dados do candidato.
        curriculo_path: caminho do arquivo de currículo (PDF).
        debug: se True, mantém o navegador visível, não envia a candidatura
            e o mantém aberto ao final (10s).
        delay: pausa em segundos após cada interação com o formulário.
        on_progress: callback opcional chamado a cada evento de progresso
            (dict serializável: status/etapa/timestamp + detalhes).

    Returns:
        dict com o resultado final:
            - sucesso: {"status": "completed", "site", "url", "log", "duracao_seg"}
            - falha:   {"status": "error", "site", "url", "log", "duracao_seg", "erro"}
    """
    inicio = time.time()

    if site not in SITES_REGISTRY:
        erro = f"Site '{site}' não registrado no sistema."
        emitir_seguro(on_progress, STATUS_ERROR, "erro", erro=erro, site=site)
        return {
            "status": STATUS_ERROR,
            "site": site,
            "url": url_vaga,
            "log": erro,
            "duracao_seg": round(time.time() - inicio, 2),
            "erro": erro,
        }

    engine = BrowserEngine(headless=not debug, debug=debug, delay=delay, on_progress=on_progress)
    with capturar_log() as stream:
        try:
            emitir_seguro(on_progress, STATUS_PROCESSING, "started", site=site, url=url_vaga)
            # Padroniza as chaves do YAML (aliases pt→en) antes de chegar ao site
            dados = normalizar(dados)
            SITES_REGISTRY[site](engine, url_vaga, dados, curriculo_path)
            duracao = round(time.time() - inicio, 2)
            emitir_seguro(on_progress, STATUS_COMPLETED, "concluido", duracao_seg=duracao)
            return {
                "status": STATUS_COMPLETED,
                "site": site,
                "url": url_vaga,
                "log": stream.getvalue().strip(),
                "duracao_seg": duracao,
            }
        except Exception as e:
            duracao = round(time.time() - inicio, 2)
            logger.exception(f"[FLUXO] site={site} | status=erro | erro={e}")
            emitir_seguro(on_progress, STATUS_ERROR, "erro", erro=str(e), duracao_seg=duracao)
            return {
                "status": STATUS_ERROR,
                "site": site,
                "url": url_vaga,
                "log": stream.getvalue().strip(),
                "duracao_seg": duracao,
                "erro": str(e),
            }
        finally:
            engine.wait_before_close()
            engine.close()
