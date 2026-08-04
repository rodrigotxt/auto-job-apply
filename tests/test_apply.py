from unittest.mock import MagicMock

import pytest

import auto_job_apply
from auto_job_apply import apply


@pytest.fixture
def mock_engine(monkeypatch):
    engine = MagicMock()
    engine.debug = False
    engine.page = MagicMock()
    engine.relatorio_campos_nao_preenchidos.return_value = []
    monkeypatch.setattr(auto_job_apply, "BrowserEngine", lambda **kwargs: engine)
    return engine


def test_apply_inhire_mocked(mock_engine):
    dados = {
        "nome": "Rodrigo Exemplo",
        "email": "rodrigo@exemplo.com",
        "disponibilidade_presencial": "Sim",
    }
    curriculo = "caminho/do/curriculo.pdf"
    url = "https://inhire.com/vaga/1"

    resultado = apply("inhire", url, dados, curriculo)

    assert resultado["status"] == "completed"
    assert "log" in resultado
    assert "duracao_seg" in resultado
    mock_engine.navigate.assert_called_with(url)
    # Campo obrigatório 'Disponibilidade para trabalho presencial' é selecionado (force=True)
    mock_engine.click.assert_any_call("input[name='workModel'][value='true']", force=True)


def test_apply_debug_nao_submete(mock_engine):
    mock_engine.debug = True
    dados = {"nome": "Rodrigo Exemplo", "email": "rodrigo@exemplo.com"}

    resultado = apply("inhire", "https://inhire.com/vaga/1", dados, "curriculo.pdf", debug=True)

    assert resultado["status"] == "completed"
    # Em debug não deve clicar em botão de submit
    clicks = [c.args[0] for c in mock_engine.click.call_args_list]
    assert not any("submit" in str(sel) or "Continuar" in str(sel) for sel in clicks)
    # Deve disparar o alerta de sucesso
    assert "alert" in str(mock_engine.evaluate.call_args)


def test_apply_on_progress(mock_engine):
    eventos = []
    dados = {"nome": "Rodrigo Exemplo", "email": "rodrigo@exemplo.com"}

    resultado = apply(
        "inhire",
        "https://inhire.com/vaga/1",
        dados,
        "curriculo.pdf",
        on_progress=eventos.append,
    )

    assert resultado["status"] == "completed"
    assert eventos[0]["status"] == "processing"
    assert eventos[0]["etapa"] == "started"
    assert eventos[-1]["status"] == "completed"
    assert eventos[-1]["etapa"] == "concluido"
    # Eventos por campo são emitidos (a engine mockada não emite; o apply emite started/completed)
    assert any(e["etapa"] == "started" for e in eventos)


def test_apply_requer_nome_completo(mock_engine):
    resultado = apply("inhire", "https://inhire.com/vaga/1", {"nome": "Rodrigo"}, "curriculo.pdf")

    assert resultado["status"] == "error"
    assert "nome e sobrenome" in resultado["erro"]


def test_apply_campo_obrigatorio_nao_encontrado(mock_engine):
    # Nenhum seletor existe na página (nem fallback por label): nome é obrigatório
    mock_engine.exists.side_effect = lambda sel: False
    mock_engine.campo_por_label.return_value = None
    resultado = apply(
        "inhire", "https://inhire.com/vaga/1", {"nome": "Rodrigo Exemplo"}, "curriculo.pdf"
    )

    assert resultado["status"] == "error"
    assert "CAMPO-NAO-ENCONTRADO" in resultado["erro"]


def test_apply_disponibilidade_ausente_ignora_e_segue(mock_engine):
    # Vaga sem a pergunta de disponibilidade presencial: o radio workModel não existe
    mock_engine.max_attempts = 2
    mock_engine.retry_delay = 0.0
    mock_engine.exists.side_effect = lambda sel: "workModel" not in sel
    dados = {"nome": "Rodrigo Exemplo", "email": "rodrigo@exemplo.com"}

    resultado = apply("inhire", "https://inhire.com/vaga/1", dados, "curriculo.pdf")

    # Fluxo conclui mesmo sem o campo
    assert resultado["status"] == "completed"
    assert "disponibilidade-presencial" in resultado["log"]
    assert "ignorado" in resultado["log"]
    # Nenhum clique em workModel foi tentado
    clicks = [c.args[0] for c in mock_engine.click.call_args_list]
    assert not any("workModel" in str(sel) for sel in clicks)


def test_apply_site_invalido():
    resultado = apply("site_invalido", "http://x.com", {}, "")

    assert resultado["status"] == "error"
    assert "não registrado" in resultado["erro"]


def test_apply_submit_desabilitado_retorna_erro(mock_engine):
    # Botão de submit existe mas permanece desabilitado (ex.: contractType não preenchido)
    mock_engine.wait_enabled.return_value = False
    mock_engine.relatorio_campos_nao_preenchidos.return_value = [
        {
            "name": "contractType",
            "id": None,
            "label": "Tipo de contrato",
            "required": True,
            "tag": "select",
            "type": "select-one",
        }
    ]
    dados = {"nome": "Rodrigo Exemplo", "email": "rodrigo@exemplo.com"}

    resultado = apply("inhire", "https://inhire.com/vaga/1", dados, "curriculo.pdf")

    assert resultado["status"] == "error"
    assert "SUBMIT-BLOQUEADO" in resultado["erro"]
    assert "contractType" in resultado["erro"]
    # Não deve forçar o clique via JS em botão desabilitado
    evals = [str(e.args) for e in mock_engine.evaluate.call_args_list]
    assert not any("removeAttribute('disabled')" in s for s in evals)


def test_apply_submit_aguarda_habilitar_e_clica(mock_engine):
    dados = {"nome": "Rodrigo Exemplo", "email": "rodrigo@exemplo.com"}

    resultado = apply("inhire", "https://inhire.com/vaga/1", dados, "curriculo.pdf")

    assert resultado["status"] == "completed"
    mock_engine.wait_enabled.assert_called()
    clicks = [c.args[0] for c in mock_engine.click.call_args_list]
    assert any("submit" in str(sel) or "Continuar" in str(sel) for sel in clicks)


def test_apply_tipo_contrato_default_clt(mock_engine):
    # Sem chave no dados, assume CLT
    dados = {"nome": "Rodrigo Exemplo", "email": "rodrigo@exemplo.com"}

    resultado = apply("inhire", "https://inhire.com/vaga/1", dados, "curriculo.pdf")

    assert resultado["status"] == "completed"
    mock_engine.click.assert_any_call(
        "input[name='contractType'][value='CLT']", force=True
    )


def test_apply_tipo_contrato_vem_do_dados(mock_engine):
    dados = {
        "nome": "Rodrigo Exemplo",
        "email": "rodrigo@exemplo.com",
        "tipo_contrato": "PJ",
    }

    resultado = apply("inhire", "https://inhire.com/vaga/1", dados, "curriculo.pdf")

    assert resultado["status"] == "completed"
    mock_engine.click.assert_any_call(
        "input[name='contractType'][value='PJ']", force=True
    )


def test_apply_contracttype_ausente_ignora_e_segue(mock_engine):
    # Vaga sem a pergunta de tipo de contrato: o radio contractType não existe
    mock_engine.max_attempts = 2
    mock_engine.retry_delay = 0.0
    mock_engine.exists.side_effect = lambda sel: "contractType" not in sel
    dados = {"nome": "Rodrigo Exemplo", "email": "rodrigo@exemplo.com"}

    resultado = apply("inhire", "https://inhire.com/vaga/1", dados, "curriculo.pdf")

    assert resultado["status"] == "completed"
    assert "tipo-contrato" in resultado["log"]
    assert "ignorado" in resultado["log"]
    clicks = [c.args[0] for c in mock_engine.click.call_args_list]
    assert not any("contractType" in str(sel) for sel in clicks)
