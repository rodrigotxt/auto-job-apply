"""CLI para rodar uma candidatura (usada pelo `make apply`).

Modo interativo (sem argumentos):
    python3 scripts/apply_cli.py
    -> pergunta site (com lista), URL, modo debug e confirma antes de agir.

Modo direto (automação/CI, não pergunta nada):
    python3 scripts/apply_cli.py --site inhire \
        --url "https://portal.inhire.app/vagas/<id>/<slug>" [--debug]
    # compatível com a forma antiga posicional:
    python3 scripts/apply_cli.py inhire "https://portal.inhire.app/vagas/<id>/<slug>" [--debug]
"""

import argparse
import logging
import sys

import yaml

from auto_job_apply import SITES_REGISTRY, apply


def _perguntar(mensagem: str, padrao: str = "") -> str:
    """input() com padrão e tratamento de EOF (Ctrl+D) -> cancela."""
    try:
        if padrao:
            resp = input(f"{mensagem} [{padrao}]: ").strip()
            return resp or padrao
        return input(f"{mensagem}: ").strip()
    except EOFError:
        print("\nOperação cancelada.")
        sys.exit(2)


def _perguntar_sim(mensagem: str, padrao: str = "n") -> bool:
    """Pergunta sim/não. O default é a letra maiúscula na dica."""
    dica = "(S/n)" if padrao.lower().startswith("s") else "(s/N)"
    while True:
        resp = _perguntar(f"{mensagem} {dica}", padrao).lower()
        if resp in ("s", "sim"):
            return True
        if resp in ("n", "nao", "não"):
            return False
        print("Responda 's' ou 'n'.")


def _escolher_site() -> str:
    """Lista os sites registrados e deixa o usuário escolher por número ou nome."""
    sites = sorted(SITES_REGISTRY.keys())
    if not sites:
        print("Nenhum site registrado na lib. Use `make add-site NAME=<nome>`.")
        sys.exit(2)
    print("\nSites disponíveis:")
    for i, s in enumerate(sites, 1):
        print(f"  {i}) {s}")
    while True:
        resp = _perguntar("Escolha o site (número ou nome)")
        if resp.isdigit():
            idx = int(resp)
            if 1 <= idx <= len(sites):
                return sites[idx - 1]
        elif resp in SITES_REGISTRY:
            return resp
        print(f"Opção inválida. Escolha entre: {', '.join(sites)}.")


def _perguntar_url() -> str:
    while True:
        url = _perguntar("URL da vaga")
        if url.startswith(("http://", "https://")):
            return url
        print("URL inválida — deve começar com http:// ou https://")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Roda uma candidatura automatizada. Sem --site/--url, pergunta interativamente."
    )
    parser.add_argument("--site", dest="site_flag", help="Nome do site registrado (ex.: inhire)")
    parser.add_argument("--url", dest="url_flag", help="URL da vaga")
    parser.add_argument(
        "site", nargs="?", help="Nome do site registrado (forma posicional, compat)"
    )
    parser.add_argument("url", nargs="?", help="URL da vaga (forma posicional, compat)")
    parser.add_argument("--dados", default="assets/dados-de-candidatura.yaml")
    parser.add_argument("--curriculo", default="assets/curriculo.pdf")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Browser visível; não envia a candidatura (dispara alerta de sucesso)",
    )
    parser.add_argument("--delay", type=float, default=2.0, help="Delay entre campos (s)")
    args = parser.parse_args()

    site, url = args.site_flag or args.site, args.url_flag or args.url
    interativo = not site or not url
    if interativo and not sys.stdin.isatty():
        parser.error(
            "SITE e URL são obrigatórios em modo não interativo (sem terminal). "
            "Use: make apply SITE=nome URL=url"
        )

    if interativo:
        print("=== Candidatura interativa ===")
        if not site:
            site = _escolher_site()
        if not url:
            url = _perguntar_url()
        if not args.debug:
            args.debug = _perguntar_sim("Rodar em modo debug (não envia a candidatura)", padrao="n")

        acao = (
            "rodar em modo debug (nada será enviado)"
            if args.debug
            else "ENVIAR a candidatura (ação real)"
        )
        if not _perguntar_sim(f"Confirma: {acao} para {site}?", padrao="s" if args.debug else "n"):
            print("Cancelado pelo usuário.")
            return 2

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    with open(args.dados, encoding="utf-8") as f:
        dados = yaml.safe_load(f)

    print(f"\nExecutando candidatura em {site}: {url} (debug={args.debug})")
    resultado = apply(
        site, url, dados, args.curriculo, debug=args.debug, delay=args.delay
    )

    print(f"\n=== STATUS FINAL: {resultado['status']} em {resultado['duracao_seg']}s ===")
    if resultado["status"] == "error":
        print(f"ERRO: {resultado['erro']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
