.PHONY: up test lint add-site

up:
	python -m venv .venv
	. .venv/bin/activate && pip install -e .[dev]
	. .venv/bin/activate && playwright install chromium

test:
	pytest tests

lint:
	ruff check .

add-site:
	@if [ -z "$(NAME)" ]; then \
		echo "Erro: Nome do site não informado. Use: make add-site NAME=nome"; \
		exit 1; \
	fi
	@echo "Criando scaffold para: $(NAME)..."
	@echo "from ..registry import register_site\n\n@register_site(\"$(NAME)\")\ndef apply_$(NAME)(url_vaga: str, dados: dict, curriculo_path: str) -> bool:\n    \"\"\"Implementação específica para o $(NAME).\"\"\"\n    print(f\"Executando $(NAME): {url_vaga}\")\n    return True" > src/auto_job_apply/sites/$(NAME).py
	@sed -i '/# Importar módulos de sites para garantir que o registro ocorra/a from .sites import $(NAME)' src/auto_job_apply/__init__.py
	@echo "Site '$(NAME)' criado e registrado com sucesso."
