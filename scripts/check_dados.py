"""Valida o YAML de dados_candidatura contra o schema e sugere campos.

Uso:
    python3 scripts/check_dados.py [--dados assets/dados-de-candidatura.yaml]
                                   [--site quickin]

Sem erros: exit 0 (pode haver sugestões). Com erros (campo desconhecido,
tipo inválido, obrigatório ausente, data inválida): exit 1.

Com --site, também lista os campos que o site usa mas não estão no YAML
(sugestão de preenchimento) e os que não existem no schema (sugestão de
criação em schema.py) — é o mecanismo para novos sites/formulários.
"""

import argparse
import sys

import yaml

from auto_job_apply.registry import SITES_CAMPOS, SITES_REGISTRY
from auto_job_apply.schema import SCHEMA, get_schema, normalizar, sugerir_campos, validar


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida o YAML de dados do candidato contra o schema e sugere campos."
    )
    parser.add_argument("--dados", default="assets/dados-de-candidatura.yaml")
    parser.add_argument(
        "--site",
        help="Nome do site (ex.: quickin) para sugerir campos ausentes.",
    )
    args = parser.parse_args()

    with open(args.dados, encoding="utf-8") as f:
        dados = yaml.safe_load(f) or {}

    erros, avisos = validar(dados)

    if args.site:
        if args.site not in SITES_REGISTRY:
            print(f"ERRO: site '{args.site}' não registrado. Disponíveis: {sorted(SITES_REGISTRY)}")
            return 1
        _sugerir_para_site(args.site, dados, erros)

    if erros:
        print("\nERROS (corrija antes de candidatar):")
        for e in erros:
            print(f"  ✗ {e}")
        return 1

    print("✓ dados_candidatura válidos contra o schema "
          f"({len(normalizar(dados))} campo(s) informado(s)).")
    if avisos:
        print("\nAvisos (não bloqueiam):")
        for a in avisos:
            print(f"  ! {a}")
    return 0


def _sugerir_para_site(site: str, dados: dict, erros: list[str]):
    campos_declarados = SITES_CAMPOS.get(site, [])
    if not campos_declarados:
        print(
            f"\nSite '{site}': nenhum campo declarado no @register_site(campos=...). "
            "Declare a lista de chaves do schema usadas pelo site para "
            "habilitar sugestões."
        )
        return

    para_criar, para_preencher = sugerir_campos(site, dados)
    obrigatorios = set(get_schema(site)["obrigatorios"])

    print(f"\nSite '{site}' usa {len(campos_declarados)} campo(s) do schema:")
    for c in campos_declarados:
        if c not in SCHEMA:
            status = "no-schema"
        elif c not in normalizar(dados):
            status = "no-yaml"
        else:
            status = "ok"
        marca = " (obrigatório)" if c in obrigatorios else ""
        print(f"  · {c:<24} {status}{marca}")

    if para_criar:
        print("\n→ Campos usados pelo site que NÃO existem no schema (sugerir criação):")
        for c in para_criar:
            print(f"  ✚ adicione '{c}' em schema.py (SCHEMA) e no seu YAML.")
    if para_preencher:
        print("\n→ Campos do schema que o site usa mas faltam no YAML (sugerir preenchimento):")
        for c in para_preencher:
            print(f"  ✎ preencha '{c}' no seu YAML (ver schema.py para formato).")


if __name__ == "__main__":
    sys.exit(main())
