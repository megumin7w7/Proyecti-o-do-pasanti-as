"""
Módulo: scrapers/base_scraper.py
Base robusta con reintentos, estado de salud y cierre seguro.
"""
import time
from typing import Optional
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from playwright_stealth import stealth_sync
from playwright.sync_api import Error as PlaywrightError
from loguru import logger

from config.settings import USER_AGENT, MAX_RETRIES


class BaseScraper:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._inicializado = False

    def iniciar_navegador(self, headless: bool = True) -> Page:
        if self._inicializado:
            return self.page

        logger.info("🌐 Inicializando Chromium (Stealth + Resource Blocker)...")
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        )

        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=USER_AGENT,
            locale="es-PE",
            timezone_id="America/Lima",
            java_script_enabled=True
        )

        self.page = self.context.new_page()
        stealth_sync(self.page)

        def _interceptar(route):
            try:
                rt = route.request.resource_type
                if rt in {"image", "media", "font"} or any(x in route.request.url for x in ["analytics", "doubleclick", "googletagmanager", "facebook"]):
                    route.abort()
                else:
                    route.continue_()
            except PlaywrightError:
                pass

        self.page.route("**/*", _interceptar)

        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """)

        self._inicializado = True
        logger.info("✅ Navegador base iniciado")
        return self.page

    def navegar_a(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 40000) -> bool:
        for intento in range(MAX_RETRIES):
            try:
                self.page.goto(url, wait_until=wait_until, timeout=timeout)
                self.page.wait_for_timeout(600)
                return True
            except Exception as e:
                logger.warning(f"⚠️ Navegación fallida ({intento + 1}/{MAX_RETRIES}): {e}")
                if intento < MAX_RETRIES - 1:
                    time.sleep(2 ** intento)
                    try:
                        self.page.reload(wait_until=wait_until, timeout=timeout)
                        return True
                    except Exception:
                        continue
        return False

    def scroll_al_final(self):
        try:
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass

    def debug_snapshot(self, nombre: str = "debug"):
        try:
            if self.page and not self.page.is_closed():
                self.page.screenshot(path=f"{nombre}.png", full_page=True)
                with open(f"{nombre}.html", "w", encoding="utf-8") as f:
                    f.write(self.page.content())
                logger.warning(f"📸 Debug: {nombre}.png / {nombre}.html")
        except Exception as e:
            logger.error(f"No se pudo guardar snapshot: {e}")

    def cerrar_navegador(self):
        if not self._inicializado:
            return
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("🔒 Navegador cerrado")
        except Exception as e:
            logger.error(f"❌ Error al cerrar: {e}")
        finally:
            self._inicializado = False
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
