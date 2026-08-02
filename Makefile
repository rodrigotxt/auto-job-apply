.PHONY: up test lint add-site apply help

help:
	@echo "Comandos disponíveis:"
	@echo "  make up          - Instala ambiente virtual e dependências"
	@echo "  make test        - Roda todos os testes unitários com pytest"
	@echo "  make lint        - Roda ruff para análise de código"
	@echo "  make add-site NAME=<nome> - Cria scaffold para um novo site"
	@echo "  make apply SITE=<nome> URL=<url> [DEBUG=1] - Roda automação (DEBUG=1: browser visível, delay 2s, aberto 10s ao final)"
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
	@echo "import logging; logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'); from auto_job_apply import apply; import yaml; \
	dados = yaml.safe_load(open('assets/dados-de-candidatura.yaml')); \
	apply('$(SITE)', '$(URL)', dados, 'assets/curriculo.pdf', debug=$(if $(DEBUG),True,False), delay=2)" > temp_run.py
	. .venv/bin/activate && python3 temp_run.py
	@rm temp_run.py
