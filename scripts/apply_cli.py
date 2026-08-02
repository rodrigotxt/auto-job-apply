"""CLI para rodar uma candidatura (usada pelo `make apply`).

Exemplo:
    python3 scripts/apply_cli.py inhire "https://portal.inhire.app/vagas/<id>/<slug>" --debug
"""

import argparse
import logging
import sys

import yaml

from auto_job_apply import apply


def main() -> int:
    parser = argparse.ArgumentParser(description="Roda uma candidatura automatizada.")
    parser.add_argument("site", help="Nome do site registrado (ex.: inhire)")
    parser.add_argument("url", help="URL da vaga")
    parser.add_argument("--dados", default="assets/dados-de-candidatura.yaml")
    parser.add_argument("--curriculo", default="assets/curriculo.pdf")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Browser visível; não envia a candidatura (dispara alerta de sucesso)",
    )
    parser.add_argument("--delay", type=float, default=2.0, help="Delay entre campos (s)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    with open(args.dados, encoding="utf-8") as f:
        dados = yaml.safe_load(f)

    resultado = apply(
        args.site, args.url, dados, args.curriculo, debug=args.debug, delay=args.delay
    )

    print(f"\n=== STATUS FINAL: {resultado['status']} em {resultado['duracao_seg']}s ===")
    if resultado["status"] == "error":
        print(f"ERRO: {resultado['erro']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
