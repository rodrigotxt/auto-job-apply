from typing import Any, Callable
from .engine import BrowserEngine

# Definimos o tipo de um executor
ExecutorFunc = Callable[[BrowserEngine, str, dict[str, Any], str], bool]

# Dicionário de registro central
SITES_REGISTRY: dict[str, ExecutorFunc] = {}

def register_site(name: str) -> Callable[[ExecutorFunc], ExecutorFunc]:
    """Decorator para registrar um executor de site."""
    def decorator(func: ExecutorFunc) -> ExecutorFunc:
        SITES_REGISTRY[name] = func
        return func
    return decorator
