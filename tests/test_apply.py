from unittest.mock import MagicMock
from auto_job_apply import apply

def test_apply_inhire_mocked():
    # Mock do BrowserEngine
    mock_engine = MagicMock()
    
    # Dados de teste
    dados = {
        "nome": "Rodrigo",
        "email": "rodrigo@exemplo.com"
    }
    curriculo = "caminho/do/curriculo.pdf"
    url = "https://inhire.com/vaga/1"
    
    # Chamada (aqui precisaríamos mockar o BrowserEngine dentro da apply ou mudar a injeção)
    # Como a apply instancia o engine, vamos mockar a classe Engine na função apply
    
    import auto_job_apply
    original_engine = auto_job_apply.BrowserEngine
    auto_job_apply.BrowserEngine = lambda: mock_engine
    
    try:
        resultado = apply("inhire", url, dados, curriculo)
        
        # Validações
        assert resultado is True
        mock_engine.navigate.assert_called_with(url)
        
    finally:
        auto_job_apply.BrowserEngine = original_engine

def test_apply_invalid_site():
    try:
        apply("site_invalido", "http://x.com", {}, "")
    except ValueError as e:
        assert str(e) == "Site 'site_invalido' não registrado no sistema."
