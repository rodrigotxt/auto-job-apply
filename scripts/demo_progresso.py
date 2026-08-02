"""Demonstração da saída da função: eventos on_progress + retorno final.

Roda em modo debug (não envia candidatura). Exibe cada evento JSON em
tempo real e o dict de resultado final.

Uso:
    python3 scripts/demo_progresso.py [SITE] [URL]
    make demo                      # usa a vaga padrão
    make demo SITE=inhire URL=<url>
"""

import argparse
import json
import logging
import sys

import yaml

from auto_job_apply import apply

DEFAULT_SITE = "inhire"
DEFAULT_URL = (
    "https://v360.inhire.app/vagas/9865a22d-9a7d-4d11-b5f5-cfd5d90a1201/"
    "estagio-desenvolvedor-full-stack-seguranca"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo dos eventos de progresso.")
    parser.add_argument("site", nargs="?", default=DEFAULT_SITE)
    parser.add_argument("url", nargs="?", default=DEFAULT_URL)
    parser.add_argument("--dados", default="assets/dados-de-candidatura.yaml")
    parser.add_argument("--curriculo", default="assets/curriculo.pdf")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    with open(args.dados, encoding="utf-8") as f:
        dados = yaml.safe_load(f)

    def on_progress(evt: dict):
        print(json.dumps(evt, ensure_ascii=False))

    print(">>> Eventos de progresso (on_progress):")
    resultado = apply(
        args.site, args.url, dados, args.curriculo, debug=True, on_progress=on_progress
    )

    print("\n>>> Retorno final (dict):")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
