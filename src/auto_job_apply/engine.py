from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

class BrowserEngine:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = sync_playwright().start()
        self.browser: Browser = self.playwright.chromium.launch(headless=self.headless)
        self.context: BrowserContext = self.browser.new_context()
        self.page: Page = self.context.new_page()

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

    def click(self, selector: str):
        self.wait_for_selector(selector)
        self.page.click(selector)

    def force_upload(self, selector: str, file_path: str):
        """Faz upload mesmo em inputs de arquivo ocultos (padrão comum em formulários estilizados)."""
        self.page.set_input_files(selector, file_path)

    def screenshot(self, path: str):
        self.page.screenshot(path=path)
