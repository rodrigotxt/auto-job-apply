from ..registry import register_site
from ..engine import BrowserEngine

@register_site("gupy")
def apply_gupy(engine: BrowserEngine, url_vaga: str, dados: dict, curriculo_path: str) -> bool:
    """Implementação específica para o Gupy."""
    print(f"Executando Gupy: {url_vaga}")
    engine.navigate(url_vaga)
    return True
