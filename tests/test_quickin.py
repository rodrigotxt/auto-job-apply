from unittest.mock import MagicMock

import pytest

import auto_job_apply
from auto_job_apply import SITES_REGISTRY, apply


@pytest.fixture
def mock_engine(monkeypatch):
    engine = MagicMock()
    engine.debug = False
    engine.page = MagicMock()
    engine.max_attempts = 3
    engine.retry_delay = 0.0
    engine.relatorio_campos_nao_preenchidos.return_value = []
    # Datepicker abre na visão de ano: faixa retornada precisa conter o ano alvo
    engine.evaluate.return_value = "1990 - 1999"
    monkeypatch.setattr(auto_job_apply, "BrowserEngine", lambda **kwargs: engine)
    return engine


def _dados_base() -> dict:
    return {
        "nome": "Rodrigo Exemplo",
        "email": "rodrigo@exemplo.com",
        "telefone": "(41) 95555-5555",
        "data_nascimento": "15/03/1990",
        "genero": "feminino",
        "cidade": "Curitiba",
        "estado": "PR",
    }


URL = "https://jobs.quickin.io/iesde/jobs/6a732a038e38610013d39d59"


def test_apply_quickin_mocked(mock_engine):
    dados = _dados_base()

    resultado = apply("quickin", URL, dados, "caminho/do/curriculo.pdf")

    assert resultado["status"] == "completed"
    assert "log" in resultado
    assert "duracao_seg" in resultado
    mock_engine.navigate.assert_called_with(URL)
    # Campos obrigatórios são preenchidos
    mock_engine.fill_field.assert_any_call("#name", "Rodrigo Exemplo")
    mock_engine.fill_field.assert_any_call("#email", "rodrigo@exemplo.com")
    # Currículo anexado e consentimento LGPD marcado
    mock_engine.force_upload.assert_called_with("#validatedCustomFile", "caminho/do/curriculo.pdf")
    mock_engine.check.assert_any_call("#consent")
    # Submete clicando em Finalizar
    mock_engine.click.assert_any_call("button[type='submit']:has-text('Finalizar')")


def test_apply_quickin_registrado():
    assert "quickin" in SITES_REGISTRY


def test_apply_quickin_debug_nao_submete(mock_engine):
    mock_engine.debug = True
    dados = _dados_base()

    resultado = apply("quickin", URL, dados, "curriculo.pdf", debug=True)

    assert resultado["status"] == "completed"
    # Em debug não deve clicar no botão de submit
    clicks = [c.args[0] for c in mock_engine.click.call_args_list]
    assert not any("submit" in str(sel) or "Finalizar" in str(sel) for sel in clicks)
    # Deve disparar o alerta de sucesso
    assert "alert" in str(mock_engine.evaluate.call_args)


def test_apply_quickin_requer_nome_completo(mock_engine):
    dados = _dados_base()
    dados["nome"] = "Rodrigo"

    resultado = apply("quickin", URL, dados, "curriculo.pdf")

    assert resultado["status"] == "error"
    assert "nome e sobrenome" in resultado["erro"]


def test_apply_quickin_data_nascimento_invalida(mock_engine):
    dados = _dados_base()
    dados["data_nascimento"] = "1990-03-15"

    resultado = apply("quickin", URL, dados, "curriculo.pdf")

    assert resultado["status"] == "error"
    assert "dd/mm/aaaa" in resultado["erro"]


def test_apply_quickin_campo_obrigatorio_nao_encontrado(mock_engine):
    # Nenhum seletor existe na página: o formulário nem carrega (#name ausente)
    mock_engine.exists.side_effect = lambda sel: False
    dados = _dados_base()

    resultado = apply("quickin", URL, dados, "curriculo.pdf")

    assert resultado["status"] == "error"
    assert "CAMPO-NAO-ENCONTRADO" in resultado["erro"]


def test_apply_quickin_genero_mapeado(mock_engine):
    dados = _dados_base()
    dados["genero"] = "feminino"

    apply("quickin", URL, dados, "curriculo.pdf")

    mock_engine.check.assert_any_call("#female")


def test_apply_quickin_genero_default_prefiro_nao_dizer(mock_engine):
    dados = _dados_base()
    del dados["genero"]

    apply("quickin", URL, dados, "curriculo.pdf")

    mock_engine.check.assert_any_call("#prefer_not_to_say")


def test_apply_quickin_pcd_mapeado(mock_engine):
    dados = _dados_base()
    dados["pcd"] = ["auditiva", "física"]

    apply("quickin", URL, dados, "curriculo.pdf")

    mock_engine.check.assert_any_call("#hearing")
    mock_engine.check.assert_any_call("#physical")


def test_apply_quickin_pais_select(mock_engine):
    dados = _dados_base()

    apply("quickin", URL, dados, "curriculo.pdf")

    mock_engine.select_option.assert_called_with("#country", "BR")


def test_apply_quickin_telefone_so_digitos(mock_engine):
    dados = _dados_base()

    apply("quickin", URL, dados, "curriculo.pdf")

    # Campo com máscara: digita tecla a tecla apenas os dígitos
    mock_engine.type_text.assert_any_call("input[placeholder='00 00000-0000']", "41955555555")


def test_apply_quickin_cidade_formato_inhire(mock_engine):
    # "Cidade - UF" (formato inhire) é separado em cidade e estado
    dados = _dados_base()
    dados["cidade"] = "Sao Jose - SC"
    del dados["estado"]

    apply("quickin", URL, dados, "curriculo.pdf")

    mock_engine.fill_field.assert_any_call("#city", "Sao Jose")
    mock_engine.fill_field.assert_any_call("#region", "SC")
