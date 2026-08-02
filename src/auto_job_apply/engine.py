import time

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright


class BrowserEngine:
    def __init__(self, headless: bool = False, debug: bool = False, delay: float = 0.0):
        self.headless = headless
        self.debug = debug
        self.delay = delay
        self.playwright = sync_playwright().start()
        self.browser: Browser = self.playwright.chromium.launch(headless=self.headless)
        self.context: BrowserContext = self.browser.new_context()
        self.page: Page = self.context.new_page()

    def _pause(self):
        """Aguarda o delay configurado (modo debug)."""
        if self.delay > 0:
            time.sleep(self.delay)

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

    def wait_for_selector(self, selector: str, timeout: int = 5000):
        self.page.wait_for_selector(selector, timeout=timeout)

    def fill_field(self, selector: str, value: str):
        self.wait_for_selector(selector)
        self.page.fill(selector, value)
        self._pause()

    def click(self, selector: str):
        self.wait_for_selector(selector)
        self.page.click(selector)
        self._pause()

    def force_upload(self, selector: str, file_path: str):
        """Faz upload mesmo em inputs de arquivo ocultos (comum em formulários estilizados)."""
        self.page.set_input_files(selector, file_path)
        self._pause()

    def screenshot(self, path: str):
        self.page.screenshot(path=path)
