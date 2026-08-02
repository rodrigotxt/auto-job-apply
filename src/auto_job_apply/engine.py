import logging
import time

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

logger = logging.getLogger(__name__)


class BrowserEngine:
    def __init__(
        self,
        headless: bool = False,
        debug: bool = False,
        delay: float = 0.0,
        max_attempts: int = 5,
        retry_delay: float = 1.0,
    ):
        self.headless = headless
        self.debug = debug
        self.delay = delay
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.playwright = sync_playwright().start()
        self.browser: Browser = self.playwright.chromium.launch(headless=self.headless)
        self.context: BrowserContext = self.browser.new_context()
        self.page: Page = self.context.new_page()

    def _pause(self):
        """Aguarda o delay configurado (modo debug)."""
        if self.delay > 0:
            time.sleep(self.delay)

    def _retry(self, fn, *args, **kwargs):
        """Executa fn com até max_attempts tentativas, aguardando retry_delay entre elas."""
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001 - retry genérico de interação com a página
                last_error = e
                if attempt < self.max_attempts:
                    logger.warning(f"Tentativa {attempt}/{self.max_attempts} falhou: {e}")
                    time.sleep(self.retry_delay)
        raise last_error

    def wait_before_close(self, seconds: float = 15.0):
        """Mantém o navegador aberto por alguns segundos (modo debug, browser visível)."""
        if not self.headless:
            time.sleep(seconds)

    def close(self):
        self.page.close()
        self.browser.close()
        self.playwright.stop()

    def navigate(self, url: str):
        self.page.goto(url)

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

    def click(self, selector: str):
        """Clica em um elemento com retry limitado."""

        def _click():
            self.page.click(selector, timeout=3000)

        self._retry(_click)
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
