.PHONY: up test lint add-site apply demo help

help:
	@echo "Comandos disponíveis:"
	@echo "  make up          - Instala ambiente virtual e dependências"
	@echo "  make test        - Roda todos os testes unitários com pytest"
	@echo "  make lint        - Roda ruff para análise de código"
	@echo "  make add-site NAME=<nome> - Cria scaffold para um novo site"
	@echo "  make apply SITE=<nome> URL=<url> [DEBUG=1] - Roda automação (DEBUG=1: browser visível, delay 2s, aberto 10s ao final)"
	@echo "  make demo [SITE=...] [URL=...] - Demonstra eventos de progresso e retorno (não envia)"
	@echo "  make help        - Mostra esta ajuda"

up:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -e .[dev]
	. .venv/bin/activate && playwright install chromium

test:
	. .venv/bin/activate && pytest tests

lint:
	. .venv/bin/activate && ruff check .

add-site:
	@if [ -z "$(NAME)" ]; then \
		echo "Erro: Nome do site não informado. Use: make add-site NAME=nome"; \
		exit 1; \
	fi
	@echo "Criando scaffold para: $(NAME)..."
	@echo "from ..registry import register_site\nfrom ..engine import BrowserEngine\n\n@register_site(\"$(NAME)\")\ndef apply_$(NAME)(engine: BrowserEngine, url_vaga: str, dados: dict, curriculo_path: str) -> bool:\n    \"\"\"Implementação específica para o $(NAME).\"\"\"\n    print(f\"Executando $(NAME): {url_vaga}\")\n    return True" > src/auto_job_apply/sites/$(NAME).py
	@sed -i '/# Importar módulos de sites para garantir que o registro ocorra/a from .sites import $(NAME)' src/auto_job_apply/__init__.py
	@echo "Site '$(NAME)' criado e registrado com sucesso."

apply:
	@if [ -z "$(SITE)" ] || [ -z "$(URL)" ]; then \
		echo "Erro: SITE e URL são obrigatórios. Use: make apply SITE=nome URL=url"; \
		exit 1; \
	fi
	@if [ ! -f "assets/curriculo.pdf" ]; then \
		echo "Aviso: assets/curriculo.pdf não encontrado. O upload falhará."; \
	fi
	. .venv/bin/activate && python3 scripts/apply_cli.py "$(SITE)" "$(URL)" $(if $(DEBUG),--debug,)

demo:
	@if [ -n "$(SITE)" ] && [ -n "$(URL)" ]; then \
		. .venv/bin/activate && python3 scripts/demo_progresso.py "$(SITE)" "$(URL)"; \
	else \
		. .venv/bin/activate && python3 scripts/demo_progresso.py; \
	fi
