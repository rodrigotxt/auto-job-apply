from unittest.mock import MagicMock

import pytest

import auto_job_apply
from auto_job_apply import apply


@pytest.fixture
def mock_engine(monkeypatch):
    engine = MagicMock()
    engine.debug = False
    engine.page = MagicMock()
    monkeypatch.setattr(auto_job_apply, "BrowserEngine", lambda **kwargs: engine)
    return engine


def test_apply_inhire_mocked(mock_engine):
    dados = {"nome": "Rodrigo Exemplo", "email": "rodrigo@exemplo.com"}
    curriculo = "caminho/do/curriculo.pdf"
    url = "https://inhire.com/vaga/1"

    resultado = apply("inhire", url, dados, curriculo)

    assert resultado is True
    mock_engine.navigate.assert_called_with(url)


def test_apply_debug_nao_submete(mock_engine):
    mock_engine.debug = True
    dados = {"nome": "Rodrigo Exemplo", "email": "rodrigo@exemplo.com"}

    resultado = apply("inhire", "https://inhire.com/vaga/1", dados, "curriculo.pdf", debug=True)

    assert resultado is True
    # Em debug não deve clicar em botão de submit
    clicks = [c.args[0] for c in mock_engine.click.call_args_list]
    assert not any("submit" in str(sel) or "Continuar" in str(sel) for sel in clicks)
    # Deve disparar o alerta de sucesso
    assert "alert" in str(mock_engine.evaluate.call_args)


def test_apply_requer_nome_completo(mock_engine):
    with pytest.raises(ValueError, match="nome e sobrenome"):
        apply("inhire", "https://inhire.com/vaga/1", {"nome": "Rodrigo"}, "curriculo.pdf")


def test_apply_site_invalido():
    with pytest.raises(ValueError, match="não registrado"):
        apply("site_invalido", "http://x.com", {}, "")
