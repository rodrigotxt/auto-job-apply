from unittest.mock import MagicMock

import pytest

import auto_job_apply
from auto_job_apply import apply


@pytest.fixture
def mock_engine(monkeypatch):
    engine = MagicMock()
    monkeypatch.setattr(auto_job_apply, "BrowserEngine", lambda **kwargs: engine)
    return engine


def test_apply_inhire_mocked(mock_engine):
    dados = {"nome": "Rodrigo Exemplo", "email": "rodrigo@exemplo.com"}
    curriculo = "caminho/do/curriculo.pdf"
    url = "https://inhire.com/vaga/1"

    resultado = apply("inhire", url, dados, curriculo)

    assert resultado is True
    mock_engine.navigate.assert_called_with(url)


def test_apply_requer_nome_completo(mock_engine):
    with pytest.raises(ValueError, match="nome e sobrenome"):
        apply("inhire", "https://inhire.com/vaga/1", {"nome": "Rodrigo"}, "curriculo.pdf")


def test_apply_site_invalido():
    with pytest.raises(ValueError, match="não registrado"):
        apply("site_invalido", "http://x.com", {}, "")
