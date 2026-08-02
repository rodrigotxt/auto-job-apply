from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

class BrowserEngine:
    def __init__(self, headless: bool = True):
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

    def fill_field(self, selector: str, value: str):
        self.page.fill(selector, value)

    def click(self, selector: str):
        self.page.click(selector)
