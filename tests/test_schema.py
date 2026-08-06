import logging
from unittest.mock import MagicMock

import pytest
import yaml

import auto_job_apply
from auto_job_apply import apply
from auto_job_apply.registry import SITES_CAMPOS, SITES_REGISTRY
from auto_job_apply.schema import (
    SCHEMA,
    _campos_avistados,
    normalizar,
    obter,
    sugerir_campos,
    validar,
)


@pytest.fixture
def mock_engine(monkeypatch):
    engine = MagicMock()
    engine.debug = False
    engine.page = MagicMock()
    engine.max_attempts = 3
    engine.retry_delay = 0.0
    engine.relatorio_campos_nao_preenchidos.return_value = []
    engine.evaluate.return_value = "1990 - 1999"
    monkeypatch.setattr(auto_job_apply, "BrowserEngine", lambda **kwargs: engine)
    return engine


def _yaml_exemplo() -> dict:
    with open("assets/dados-de-candidatura.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# normalizar / aliases
# ---------------------------------------------------------------------------
def test_normalizar_aliases_pt_para_en():
    dados = {"nome": "Maria Silva", "telefone": "11999999999", "pretensao_salarial": 4500}

    out = normalizar(dados)

    assert out["full_name"] == "Maria Silva"
    assert out["phone"] == "11999999999"
    assert out["salary_expectation"] == 4500
    assert "nome" not in out


def test_normalizar_prioriza_chave_inglesa():
    dados = {"full_name": "Maria EN", "nome": "Maria PT"}

    out = normalizar(dados)

    assert out["full_name"] == "Maria EN"


def test_normalizar_mantem_chave_desconhecida():
    dados = {"campo_novo_qualquer": "x"}

    out = normalizar(dados)

    assert out["campo_novo_qualquer"] == "x"


# ---------------------------------------------------------------------------
# obter / sugestão de criação
# ---------------------------------------------------------------------------
def test_obter_campo_conhecido():
    assert obter({"full_name": "Maria"}, "full_name") == "Maria"
    assert obter({}, "full_name", "default") == "default"


def test_obter_campo_desconhecido_sugere_criacao(caplog):
    with caplog.at_level(logging.WARNING, logger="auto_job_apply.schema"):
        obter({}, "campo_inventado")

    assert any("[SCHEMA-SUGESTAO]" in r.message for r in caplog.records)
    assert any("campo_inventado" in r.message for r in caplog.records)
    assert any("schema.py" in r.message for r in caplog.records)


def test_obter_sugestao_logada_uma_vez(caplog):
    _campos_avistados.clear()  # estado global do módulo persiste entre testes
    with caplog.at_level(logging.WARNING, logger="auto_job_apply.schema"):
        obter({}, "campo_inventado")
        obter({}, "campo_inventado")

    sugestoes = [r for r in caplog.records if "[SCHEMA-SUGESTAO]" in r.message]
    assert len(sugestoes) == 1
    _campos_avistados.clear()


# ---------------------------------------------------------------------------
# validar
# ---------------------------------------------------------------------------
def test_validar_yaml_exemplo_sem_erros():
    erros, avisos = validar(_yaml_exemplo())

    assert erros == []
    assert avisos == []


def test_validar_campo_desconhecido():
    erros, _ = validar({"full_name": "Maria Silva", "carteira_motorista": "B"})

    assert any("carteira_motorista" in e and "não existe no schema" in e for e in erros)


def test_validar_obrigatorios_ausentes():
    erros, _ = validar({"phone": "11999999999"})

    assert any("full_name" in e for e in erros)
    assert any("email" in e for e in erros)


def test_validar_tipo_invalido():
    erros, _ = validar({"full_name": "Maria Silva", "email": "m@x.com", "experience_years": "oito"})

    assert any("experience_years" in e and "número" in e for e in erros)


def test_validar_data_invalida():
    erros, _ = validar({"full_name": "Maria Silva", "email": "m@x.com", "birth_date": "1990-03-15"})

    assert any("birth_date" in e and "dd/mm/aaaa" in e for e in erros)


def test_validar_valor_fora_das_opcoes_e_aviso():
    _, avisos = validar({"full_name": "Maria Silva", "email": "m@x.com", "gender": "alien"})

    assert any("gender" in a and "opções" in a for a in avisos)


# ---------------------------------------------------------------------------
# sugerir_campos (site novo buscando no arquivo)
# ---------------------------------------------------------------------------
def test_sites_declaram_campos():
    assert "quickin" in SITES_CAMPOS and "inhire" in SITES_CAMPOS
    for site in ("quickin", "inhire"):
        assert SITES_CAMPOS[site], f"{site} deveria declarar campos"
        for chave in SITES_CAMPOS[site]:
            assert chave in SCHEMA, f"{site} usa '{chave}' que não existe no schema"


def test_sugerir_campos_quickin_com_yaml_exemplo():
    para_criar, para_preencher = sugerir_campos("quickin", _yaml_exemplo())

    assert para_criar == []
    assert "full_name" not in para_preencher
    assert "email" not in para_preencher


def test_sugerir_campos_aponta_faltantes():
    para_criar, para_preencher = sugerir_campos("quickin", {"full_name": "Maria Silva"})

    assert "email" in para_preencher
    assert "birth_date" in para_preencher


def test_sugerir_campos_campo_fora_do_schema():
    # Simula site que usa chave ainda não criada no schema
    import auto_job_apply.registry as registry

    registry.SITES_CAMPOS["site_teste"] = ["full_name", "campo_futuro"]

    try:
        para_criar, para_preencher = sugerir_campos("site_teste", {"full_name": "Maria"})
        assert para_criar == ["campo_futuro"]
        assert para_preencher == []
    finally:
        del registry.SITES_CAMPOS["site_teste"]


# ---------------------------------------------------------------------------
# integração: apply com YAML em inglês (padrão novo)
# ---------------------------------------------------------------------------
def test_apply_quickin_com_chaves_inglesas(mock_engine):
    dados = {
        "full_name": "Rodrigo Exemplo",
        "email": "rodrigo@exemplo.com",
        "phone": "(41) 95555-5555",
        "birth_date": "15/03/1990",
        "gender": "female",
        "city": "Curitiba",
        "state": "PR",
        "summary": "Resumo teste",
        "consent": True,
    }
    url = "https://jobs.quickin.io/iesde/jobs/123"

    resultado = apply("quickin", url, dados, "caminho/do/curriculo.pdf")

    assert resultado["status"] == "completed"
    mock_engine.fill_field.assert_any_call("#name", "Rodrigo Exemplo")
    mock_engine.fill_field.assert_any_call("#email", "rodrigo@exemplo.com")
    mock_engine.check.assert_any_call("#consent")
    mock_engine.force_upload.assert_called_with("#validatedCustomFile", "caminho/do/curriculo.pdf")


def test_apply_inhire_com_chaves_inglesas(mock_engine):
    dados = {
        "full_name": "Rodrigo Exemplo",
        "email": "rodrigo@exemplo.com",
        "phone": "(41) 95555-5555",
        "city": "Sao Jose - SC",
        "work_model": "remote",
        "contract_type": "PJ",
    }
    url = "https://inhire.com/vaga/1"

    resultado = apply("inhire", url, dados, "curriculo.pdf")

    assert resultado["status"] == "completed"
    mock_engine.fill_field.assert_any_call("input[name='name']", "Rodrigo Exemplo")
    # remote -> disponibilidade presencial "Não"
    mock_engine.click.assert_any_call("input[name='workModel'][value='false']", force=True)
    mock_engine.click.assert_any_call("input[name='contractType'][value='PJ']", force=True)


def test_registry_tem_quickin_e_inhire():
    assert {"quickin", "inhire"} <= set(SITES_REGISTRY)
