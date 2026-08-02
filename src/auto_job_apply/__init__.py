from .registry import SITES_REGISTRY
from .engine import BrowserEngine

# Importar módulos de sites para garantir que o registro ocorra
from .sites import inhire
from .sites import gupy 

def apply(site: str, url_vaga: str, dados: dict, curriculo_path: str) -> bool:
    """Interface unificada para automação de candidaturas."""
    if site not in SITES_REGISTRY:
        raise ValueError(f"Site '{site}' não registrado no sistema.")
    
    engine = BrowserEngine()
    try:
        return SITES_REGISTRY[site](engine, url_vaga, dados, curriculo_path)
    finally:
        engine.close()
