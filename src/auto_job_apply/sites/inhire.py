from ..registry import register_site
from ..engine import BrowserEngine

@register_site("inhire")
def apply_inhire(engine: BrowserEngine, url_vaga: str, dados: dict, curriculo_path: str) -> bool:
    """Implementação específica para o inhire."""
    print(f"Executando inhire: {url_vaga}")
    engine.navigate(url_vaga)
    return True
