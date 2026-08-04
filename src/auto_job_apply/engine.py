import logging
import time

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .progresso import ProgressCallback, montar_evento

logger = logging.getLogger(__name__)


class BrowserEngine:
    def __init__(
        self,
        headless: bool = False,
        debug: bool = False,
        delay: float = 0.0,
        max_attempts: int = 3,
        retry_delay: float = 1.0,
        on_progress: ProgressCallback | None = None,
    ):
        self.headless = headless
        self.debug = debug
        self.delay = delay
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.on_progress = on_progress
        self.playwright = sync_playwright().start()
        self.browser: Browser = self.playwright.chromium.launch(headless=self.headless)
        self.context: BrowserContext = self.browser.new_context()
        self.page: Page = self.context.new_page()

    def emitir(self, status: str, etapa: str, **kwargs):
        """Emite evento de progresso (se callback registrado). Nunca levanta."""
        if not self.on_progress:
            return
        try:
            self.on_progress(montar_evento(status, etapa, **kwargs))
        except Exception as e:
            logger.warning(f"[PROGRESSO] callback falhou: {e}")

    def _pause(self):
        """Aguarda o delay configurado (modo debug)."""
        if self.delay > 0:
            time.sleep(self.delay)

    def _retry(self, fn, max_attempts=None):
        """Executa fn com até max_attempts tentativas, aguardando retry_delay entre elas."""
        attempts = max_attempts or self.max_attempts
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as e:  # noqa: BLE001 - retry genérico de interação com a página
                last_error = e
                if attempt < attempts:
                    logger.warning(f"Tentativa {attempt}/{attempts} falhou: {e}")
                    time.sleep(self.retry_delay)
        raise last_error

    def wait_before_close(self, seconds: float = 10.0):
        """Mantém o navegador aberto por alguns segundos (modo debug, browser visível)."""
        if not self.headless:
            time.sleep(seconds)

    def close(self):
        self.page.close()
        self.browser.close()
        self.playwright.stop()

    def navigate(self, url: str):
        self.page.goto(url)

    def exists(self, selector: str) -> bool:
        """Verifica se o elemento existe no DOM (sem esperar visibilidade)."""
        try:
            return self.page.locator(selector).count() > 0
        except Exception:  # noqa: BLE001 - seletor inválido conta como inexistente
            return False

    def campo_por_label(self, texto: str) -> str | None:
        """Busca um campo cujo label/aria-label/placeholder contenha o texto (case-insensitive)."""
        candidatos = [
            f"label:has-text('{texto}') input",
            f"label:has-text('{texto}') textarea",
            f"[aria-label*='{texto}' i]",
            f"input[placeholder*='{texto}' i]",
            f"textarea[placeholder*='{texto}' i]",
        ]
        for sel in candidatos:
            try:
                if self.page.locator(sel).count() > 0:
                    return sel
            except Exception:  # noqa: BLE001 - seletor inválido, tenta próximo
                continue
        return None

    def is_enabled(self, selector: str) -> bool:
        """True se o elemento existe e não está desabilitado (disabled/aria-disabled)."""
        try:
            return bool(
                self.page.evaluate(
                    """(sel) => {
                        const el = document.querySelector(sel);
                        if (!el) return false;
                        return !el.disabled && el.getAttribute('aria-disabled') !== 'true';
                    }""",
                    selector,
                )
            )
        except Exception:  # noqa: BLE001 - best-effort, trata como desabilitado
            return False

    def wait_enabled(self, selector: str, timeout: float = 10.0) -> bool:
        """Aguarda o elemento ficar habilitado (validação assíncrona do form)."""
        fim = time.time() + timeout
        while time.time() < fim:
            if self.is_enabled(selector):
                return True
            time.sleep(0.5)
        return False

    def relatorio_campos_nao_preenchidos(self) -> list[dict]:
        """Lista campos visíveis que estão vazios (para diagnóstico/IA)."""
        try:
            return self.page.evaluate(
                """() => {
                  const out = [];
                  const vistos = new Set();
                  document.querySelectorAll('input, textarea, select').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 && r.height === 0) return;  // oculto
                    if (el.type === 'radio' || el.type === 'checkbox') return;
                    if (el.name) {
                      if (vistos.has(el.name)) return;
                      vistos.add(el.name);
                    }
                    const vazio = (el.value ?? '').trim() === '';
                    if (!vazio) return;
                    const label = (
                      el.closest('label')?.textContent
                      || el.getAttribute('aria-label')
                      || el.placeholder
                      || ''
                    ).trim().slice(0, 120);
                    out.push({
                      tag: el.tagName.toLowerCase(),
                      type: el.type,
                      name: el.name || null,
                      id: el.id || null,
                      required: !!el.required || el.getAttribute('aria-required') === 'true',
                      label,
                    });
                  });
                  return out;
                }"""
            )
        except Exception as e:  # noqa: BLE001 - relatório é best-effort
            logger.warning(f"[RELATORIO] falha ao inspecionar campos: {e}")
            return []

    def wait_for_selector(self, selector: str, timeout: int = 1000):
        """Espera o elemento aparecer, com até max_attempts tentativas."""

        def _wait():
            self.page.wait_for_selector(selector, timeout=timeout)

        self._retry(_wait)

    def fill_field(self, selector: str, value: str):
        """Preenche um campo com retry limitado."""

        def _fill():
            self.page.fill(selector, value, timeout=3000)

        self._retry(_fill)
        self._pause()

    def click(self, selector: str, force: bool = False, attempts: int | None = None):
        """Clica em um elemento com retry limitado.

        force=True ignora actionability checks (útil quando um <span> estilizado
        intercepta o clique ou o input é visualmente oculto).
        """

        def _click():
            self.page.click(selector, timeout=3000, force=force)

        self._retry(_click, max_attempts=attempts)
        self._pause()

    def check(self, selector: str):
        """Marca checkbox/radio mesmo se oculto (force)."""

        def _check():
            self.page.check(selector, force=True, timeout=3000)

        self._retry(_check)
        self._pause()

    def type_text(self, selector: str, value: str, delay: float = 80):
        """Digita texto tecla a tecla (necessário em campos com máscara)."""
        self.page.type(selector, value, delay=delay)
        self._pause()

    def force_upload(self, selector: str, file_path: str):
        """Faz upload mesmo em inputs de arquivo ocultos (comum em formulários estilizados)."""

        def _upload():
            self.page.set_input_files(selector, file_path)

        self._retry(_upload)
        self._pause()

    def evaluate(self, expression: str):
        """Executa JavaScript na página (fallback para casos especiais)."""
        return self.page.evaluate(expression)

    def screenshot(self, path: str):
        self.page.screenshot(path=path)
