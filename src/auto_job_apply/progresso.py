"""Eventos de progresso e status da automação.

Define o contrato de saída da biblioteca: a função ``apply`` emite eventos
via callback ``on_progress`` e retorna um dict com o status final.
"""

import io
import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"

#: Callback recebe um dict de evento (serializável em JSON).
ProgressCallback = Callable[[dict], None]

_FORMATO_LOG = "%(asctime)s - %(levelname)s - %(message)s"


def montar_evento(status: str, etapa: str, **kwargs: Any) -> dict:
    """Monta um evento de progresso com timestamp."""
    return {"status": status, "etapa": etapa, "timestamp": time.time(), **kwargs}


def emitir_seguro(
    callback: ProgressCallback | None, status: str, etapa: str, **kwargs: Any
) -> None:
    """Chama o callback de progresso; nunca levanta.

    Uma falha no callback do consumidor não pode quebrar a automação.
    """
    if callback is None:
        return
    try:
        callback(montar_evento(status, etapa, **kwargs))
    except Exception:
        logging.getLogger(__name__).warning("[PROGRESSO] callback falhou", exc_info=True)


@contextmanager
def capturar_log():
    """Captura os logs estruturados emitidos durante a execução da automação."""
    logger = logging.getLogger("auto_job_apply")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(_FORMATO_LOG))
    logger.addHandler(handler)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)
