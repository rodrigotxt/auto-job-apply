from collections.abc import Callable
from typing import Any

from .engine import BrowserEngine

# Definimos o tipo de um executor
ExecutorFunc = Callable[[BrowserEngine, str, dict[str, Any], str], bool]

# Dicionário de registro central
SITES_REGISTRY: dict[str, ExecutorFunc] = {}

# Campos de dados_candidatura que cada site usa (para o check-dados sugerir o
# que falta no YAML / no schema.py). Preenchido via register_site(campos=...).
SITES_CAMPOS: dict[str, list[str]] = {}

# Campos que cada site EXIGE (o fluxo aborta se ausentes/vazios), além dos
# obrigatórios globais do schema (Campo.obrigatorio=True). Preenchido via
# register_site(obrigatorios=...).
SITES_OBRIGATORIOS: dict[str, list[str]] = {}


def register_site(
    name: str,
    campos: list[str] | None = None,
    obrigatorios: list[str] | None = None,
) -> Callable[[ExecutorFunc], ExecutorFunc]:
    """Decorator para registrar um executor de site.

    Args:
        name: nome do site (chave usada no apply() e no Makefile).
        campos: chaves do schema (schema.py) que o site lê dos dados do
            candidato — usadas por `make check-dados` para sugerir campos
            ausentes no YAML ou campos novos a criar no schema.
        obrigatorios: subconjunto de `campos` que o site EXIGE (form marca
            como required e o fluxo aborta se faltar). São somados aos
            obrigatórios globais do schema — veja get_schema().
    """

    def decorator(func: ExecutorFunc) -> ExecutorFunc:
        SITES_REGISTRY[name] = func
        if campos:
            SITES_CAMPOS[name] = campos
        if obrigatorios:
            SITES_OBRIGATORIOS[name] = obrigatorios
        return func

    return decorator
