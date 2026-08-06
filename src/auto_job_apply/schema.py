"""Schema dos dados do candidato (dados_candidatura).

Define o padrão único de chaves — em INGLÊS — usado por todos os sites, com o
maior número possível de campos observados em formulários de candidatura
(inhire, quickin, gupy, workable, greenhouse, etc.), organizados por seção.

Regras para contribuidores:

1. Todo site lê os dados do candidato via `obter(dados, "chave")` — nunca
   `dados["chave_solta"]`.
2. Se o site precisa de um campo que NÃO existe no `SCHEMA`, o sistema loga
   `[SCHEMA-SUGESTAO]` apontando a chave. Nesse caso:
   - adicione o campo em `SCHEMA` (com seção/tipo/descrição/exemplo);
   - declare a chave na lista `campos` do `@register_site(...)` do site.
3. `make check-dados SITE=<nome>` valida o YAML contra o schema e lista o que
   falta (campos do site ausentes no YAML, campos do YAML fora do schema).

Aliases pt→en mantêm compatibilidade com YAMLs antigos (ex.: `nome` vira
`full_name`); a normalização acontece no `apply()` antes de chegar ao site.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Formato aceito para campos do tipo "date" (dd/mm/aaaa)
_FORMATO_DATA = r"\d{1,2}/\d{1,2}/\d{4}"


@dataclass(frozen=True)
class Campo:
    """Definição de um campo do padrão de dados do candidato."""

    chave: str
    secao: str
    tipo: str = "str"
    descricao: str = ""
    exemplo: str | None = None
    opcoes: tuple[str, ...] = ()
    obrigatorio: bool = False


# ---------------------------------------------------------------------------
# Definição do schema (chaves em inglês, organizadas por seção)
# ---------------------------------------------------------------------------
_CAMPOS: list[Campo] = [
    # ---- personal ------------------------------------------------------
    Campo(
        "full_name", "personal", "str",
        "Nome completo (nome e sobrenome).", "Maria Silva",
        obrigatorio=True,
    ),
    Campo("first_name", "personal", "str", "Primeiro nome.", "Maria"),
    Campo("last_name", "personal", "str", "Sobrenome.", "Silva"),
    Campo("birth_date", "personal", "date", "Data de nascimento (dd/mm/aaaa).", "15/03/1990"),
    Campo(
        "gender", "personal", "str", "Gênero.", "female",
        ("male", "female", "other", "prefer_not_to_say"),
    ),
    Campo("pronouns", "personal", "str", "Pronomes (she/her, he/him, they/them).", "she/her"),
    Campo("cpf", "personal", "str", "CPF (Brasil).", "11144477735"),
    Campo("nationality", "personal", "str", "Nacionalidade.", "Brasileira"),
    Campo(
        "marital_status", "personal", "str", "Estado civil.", "single",
        ("single", "married", "divorced", "widowed"),
    ),
    Campo("has_disability", "personal", "bool", "Se a pessoa é PcD (sim/não).", "false"),
    Campo(
        "disabilities", "personal", "list",
        "Deficiências declaradas (lista).", '["hearing", "physical"]',
        ("hearing", "vision", "intellectual", "physical", "other"),
    ),
    Campo("photo_path", "personal", "file", "Caminho local da foto (jpg/png).", "assets/foto.jpg"),

    # ---- contact -------------------------------------------------------
    Campo(
        "email", "contact", "str", "E-mail principal.", "maria@exemplo.com",
        obrigatorio=True,
    ),
    Campo(
        "phone", "contact", "str",
        "Telefone (DDI opcional; máscaras são ignoradas).", "+55 41 95555-5555",
    ),
    Campo("phone_country_code", "contact", "str", "Código do país do telefone.", "+55"),
    Campo("alternative_phone", "contact", "str", "Telefone alternativo.", "+55 41 3333-3333"),
    Campo(
        "linkedin_url", "contact", "str",
        "URL do perfil no LinkedIn.", "https://linkedin.com/in/maria-silva",
    ),
    Campo("github_url", "contact", "str", "URL do perfil no GitHub.", "https://github.com/maria-silva"),
    Campo("portfolio_url", "contact", "str", "URL do portfólio.", "https://maria.dev"),
    Campo("website_url", "contact", "str", "URL de site pessoal.", "https://maria.dev"),

    # ---- address -------------------------------------------------------
    Campo("country", "address", "str", "País (código ISO 3166-1 alfa-2).", "BR"),
    Campo("state", "address", "str", "Estado/UF.", "SC"),
    Campo("city", "address", "str", "Cidade.", "São José"),
    Campo("neighborhood", "address", "str", "Bairro.", "Centro"),
    Campo("address", "address", "str", "Logradouro e número.", "Rua das Árvores, 55"),
    Campo("address_line2", "address", "str", "Complemento.", "Apto 12"),
    Campo("zip_code", "address", "str", "CEP.", "88101-320"),

    # ---- professional ------------------------------------------------
    Campo(
        "headline", "professional", "str",
        "Título profissional curto (cargo atual).", "Dev Sênior",
    ),
    Campo("desired_role", "professional", "str", "Cargo pretendido.", "Desenvolvedora de Software"),
    Campo(
        "summary", "professional", "str",
        "Resumo das qualificações (texto livre).", "8 anos em produtos digitais...",
    ),
    Campo("experience_years", "professional", "int", "Anos de experiência.", "8"),
    Campo(
        "skills", "professional", "list",
        "Habilidades (lista de tags).", '["Python", "FastAPI"]',
    ),
    Campo(
        "education_level", "professional", "str", "Escolaridade.", "bachelor",
        ("high_school", "technical", "associate", "bachelor", "master", "phd"),
    ),
    Campo(
        "english_level", "professional", "str", "Nível de inglês.", "advanced",
        ("basic", "intermediate", "advanced", "fluent", "native"),
    ),
    Campo("other_languages", "professional", "list", "Outros idiomas.", '["Espanhol"]'),
    Campo("salary_expectation", "professional", "float", "Pretensão salarial (número).", "4500"),
    Campo("salary_currency", "professional", "str", "Moeda da pretensão.", "BRL"),
    Campo(
        "contract_type", "professional", "str", "Tipo de contrato.", "CLT",
        ("CLT", "PJ", "internship", "trainee", "temporary", "other"),
    ),
    Campo(
        "work_model", "professional", "str", "Modelo de trabalho.", "remote",
        ("remote", "hybrid", "onsite"),
    ),
    Campo(
        "availability", "professional", "str", "Disponibilidade para início.", "immediate",
        ("immediate", "notice"),
    ),
    Campo("notice_period_days", "professional", "int", "Dias de aviso prévio.", "30"),
    Campo("willing_to_relocate", "professional", "bool", "Disposto a mudar de cidade.", "false"),
    Campo("has_driver_license", "professional", "bool", "Possui CNH.", "false"),
    Campo("driver_license_categories", "professional", "str", "Categorias da CNH.", "B"),
    Campo("has_vehicle", "professional", "bool", "Possui veículo.", "false"),

    # ---- diversity (usado por alguns sites, ex.: inhire) ------------
    Campo(
        "gender_identity", "diversity", "str",
        "Identidade de gênero (perguntas de diversidade).", "prefer_not_to_say",
        ("male", "female", "non_binary", "prefer_not_to_say"),
    ),
    Campo(
        "sexual_orientation", "diversity", "str", "Orientação sexual.", "prefer_not_to_say",
        ("heterosexual", "homosexual", "bisexual", "other", "prefer_not_to_say"),
    ),
    Campo(
        "race_ethnicity", "diversity", "str", "Raça/cor/etnia.", "prefer_not_to_say",
        ("white", "black", "brown", "asian", "indigenous", "other", "prefer_not_to_say"),
    ),
    Campo(
        "disability_identity", "diversity", "str",
        "Pessoa com deficiência (pergunta de diversidade).", "no",
        ("yes", "no", "prefer_not_to_say"),
    ),

    # ---- application (desta candidatura) ----------------------------
    Campo(
        "referral", "application", "str",
        "Nome de quem indicou (vazio = sem indicação).", "João Silva",
    ),
    Campo("how_did_you_hear", "application", "str", "Onde conheceu a vaga.", "Indeed"),
    Campo("cover_letter", "application", "str", "Carta de apresentação (texto).", "Prezados, ..."),
    Campo("consent", "application", "bool", "Autoriza o processamento dos dados (LGPD).", "true"),
    Campo(
        "resume_path", "application", "file",
        "Caminho do currículo (fallback do parâmetro).", "assets/curriculo.pdf",
    ),
    Campo(
        "additional_documents", "application", "list",
        "Outros documentos (caminhos).", '["assets/certificado.pdf"]',
    ),
]

SCHEMA: dict[str, Campo] = {c.chave: c for c in _CAMPOS}

# Aliases pt→en para retrocompatibilidade com YAMLs escritos antes do padrão.
ALIASES: dict[str, str] = {
    "nome": "full_name",
    "primeiro_nome": "first_name",
    "sobrenome": "last_name",
    "data_nascimento": "birth_date",
    "genero": "gender",
    "pronomes": "pronouns",
    "nacionalidade": "nationality",
    "estado_civil": "marital_status",
    "pcd": "disabilities",
    "foto": "photo_path",
    "telefone": "phone",
    "telefone_alternativo": "alternative_phone",
    "linkedin": "linkedin_url",
    "github": "github_url",
    "portfolio": "portfolio_url",
    "site": "website_url",
    "pais": "country",
    "estado": "state",
    "cidade": "city",
    "bairro": "neighborhood",
    "endereco": "address",
    "complemento": "address_line2",
    "cep": "zip_code",
    "cargo_pretendido": "desired_role",
    "objetivo": "desired_role",
    "resumo": "summary",
    "anos_experiencia": "experience_years",
    "habilidades": "skills",
    "escolaridade": "education_level",
    "nivel_ingles": "english_level",
    "idiomas": "other_languages",
    "pretensao_salarial": "salary_expectation",
    "moeda": "salary_currency",
    "tipo_contrato": "contract_type",
    "contrato": "contract_type",
    "modelo_trabalho": "work_model",
    "disponibilidade_presencial": "work_model",
    "disponibilidade": "availability",
    "aviso_previo_dias": "notice_period_days",
    "disposto_mudar": "willing_to_relocate",
    "possui_cnh": "has_driver_license",
    "categorias_cnh": "driver_license_categories",
    "possui_veiculo": "has_vehicle",
    "identidade_genero": "gender_identity",
    "orientacao_sexual": "sexual_orientation",
    "raca_etnia": "race_ethnicity",
    "identidade_pcd": "disability_identity",
    "indicacao": "referral",
    "indicacao_nome": "referral",
    "como_conheceu": "how_did_you_hear",
    "carta_apresentacao": "cover_letter",
    "privacidade": "consent",
    "curriculo_path": "resume_path",
    "documentos": "additional_documents",
}

# Campos cuja sugestão de criação já foi logada (evita repetir no mesmo run)
_campos_avistados: set[str] = set()


def normalizar(dados: dict[str, Any]) -> dict[str, Any]:
    """Converte aliases pt→en e retorna um dict com as chaves do padrão.

    Se o YAML tiver a chave em inglês E o alias em português, a chave em
    inglês vence (é mais específica).
    """
    saida: dict[str, Any] = {}
    for chave_original, valor in dados.items():
        chave = ALIASES.get(chave_original, chave_original)
        if chave in dados:  # chave canônica presente no YAML: prioriza
            saida[chave] = dados[chave]
        elif chave not in saida:
            saida[chave] = valor
    return saida


def obter(dados: dict[str, Any], chave: str, padrao: Any = None) -> Any:
    """Lê um campo dos dados normalizados.

    Se a chave não existe no SCHEMA, loga [SCHEMA-SUGESTAO] orientando a
    criação do campo — é o mecanismo que aponta campos novos de formulário
    para quem está criando/adaptando um site.
    """
    if chave not in SCHEMA and chave not in _campos_avistados:
        _campos_avistados.add(chave)
        logger.warning(
            f"[SCHEMA-SUGESTAO] campo '{chave}' não existe no schema de "
            "dados_candidatura. Para criá-lo: adicione em schema.py (SCHEMA) e "
            "declare em `campos` no @register_site do site."
        )
    return dados.get(chave, padrao)


def validar(dados: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Valida o YAML contra o schema.

    Returns:
        (erros, avisos): erros devem bloquear (exit != 0 em check-dados);
        avisos são sugestões (campo do schema ausente, valor fora das opções).
    """
    erros: list[str] = []
    avisos: list[str] = []
    dados = normalizar(dados)

    for chave, valor in dados.items():
        campo = SCHEMA.get(chave)
        if campo is None:
            erros.append(
                f"campo desconhecido: '{chave}' — não existe no schema. "
                "Se o site precisa dele, adicione em schema.py (SCHEMA)."
            )
            continue
        problema = _validar_tipo(campo, valor)
        if problema:
            erros.append(f"campo '{chave}': {problema}")
        elif (
            campo.opcoes
            and isinstance(valor, str)
            and not _vazio(valor)
            and valor.lower() not in {o.lower() for o in campo.opcoes}
        ):
            avisos.append(
                f"campo '{chave}': valor '{valor}' fora das opções sugeridas "
                f"{list(campo.opcoes)} (pode ser aceito pelo site mesmo assim)."
            )

    for campo in SCHEMA.values():
        if campo.obrigatorio and _vazio(dados.get(campo.chave)):
            erros.append(f"campo obrigatório ausente: '{campo.chave}' ({campo.secao})")
        elif campo.tipo == "date" and not _vazio(dados.get(campo.chave)):
            if not re.fullmatch(_FORMATO_DATA, str(dados[campo.chave]).strip()):
                erros.append(f"campo '{campo.chave}': data deve estar em dd/mm/aaaa.")

    return erros, avisos


def sugerir_campos(site: str, dados: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Campos que o site usa mas não estão nos dados do candidato.

    Returns:
        (para_criar_no_schema, para_preencher_no_yaml): o primeiro lista campos
        usados pelo site que não existem nem no schema; o segundo, campos do
        schema que o site usa mas estão ausentes/vazios no YAML.
    """
    from .registry import SITES_CAMPOS

    usados = SITES_CAMPOS.get(site, [])
    dados = normalizar(dados)
    para_criar = [c for c in usados if c not in SCHEMA]
    para_preencher = [c for c in usados if c in SCHEMA and _vazio(dados.get(c))]
    return para_criar, para_preencher


def _validar_tipo(campo: Campo, valor: Any) -> str | None:
    if campo.tipo == "str":
        if not isinstance(valor, str):
            return f"esperado str, veio {type(valor).__name__}"
    elif campo.tipo in ("int", "float"):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return f"esperado número, veio {type(valor).__name__}"
    elif campo.tipo == "bool":
        if not isinstance(valor, bool):
            return f"esperado bool (true/false), veio {type(valor).__name__}"
    elif campo.tipo == "list":
        if not isinstance(valor, list):
            return f"esperado lista, veio {type(valor).__name__}"
    elif campo.tipo == "file":
        if not isinstance(valor, str):
            return f"esperado caminho (str), veio {type(valor).__name__}"
    return None


def _vazio(valor: Any) -> bool:
    if valor is None:
        return True
    if isinstance(valor, str):
        return valor.strip() == ""
    if isinstance(valor, (list, dict)):
        return len(valor) == 0
    return False
