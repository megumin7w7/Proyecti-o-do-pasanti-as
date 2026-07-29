"""
Módulo: scrapers/base_scraper.py (100% Playwright - Sin Selenium)
"""
import time
from playwright.sync_api import sync_playwright, Page, Browser
from loguru import logger

class BaseScraper:
    """Clase base para todos los scrapers usando Playwright."""
    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.page: Page = None
        self.logger = logger
        self.logger.info("✅ BaseScraper (Playwright) inicializado")

    def debug_snapshot(self, nombre="debug"):
        """Guarda screenshot + HTML + status/URL real para depurar en CI."""
        try:
            if self.page:
                self.page.screenshot(path=f"{nombre}.png", full_page=True)
                html = self.page.content()
                with open(f"{nombre}.html", "w", encoding="utf-8") as f:
                    f.write(html)
                self.logger.warning(
                    f"📸 Debug guardado: {nombre}.png / {nombre}.html "
                    f"({len(html)} chars) | URL final: {self.page.url}"
                )
        except Exception as e:
            self.logger.error(f"No se pudo guardar debug: {e}")

    def iniciar_navegador(self, headless: bool = True):
        """Inicializa el navegador Chrome con configuraciones antibloqueo."""
        self.logger.info("🌐 Configurando Chromium con Playwright...")
        self.playwright = sync_playwright().start()
        
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        
        context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        self.page = context.new_page()
        
        # Inyectar scripts anti-detección
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)
        
        self.logger.info("✅ Navegador Playwright iniciado con éxito")
        return self.page

    def navegar_a(self, url: str, wait_until: str = "domcontentloaded"):
        """Navega a una URL y espera a que cargue."""
        self.logger.debug(f"🔗 Navegando a: {url[:80]}...")
        self.page.goto(url, wait_until=wait_until, timeout=60000)
        time.sleep(1)

    def esperar_elemento(self, selector: str, timeout: int = 15000):
        """Espera a que un elemento esté presente en la página."""
        try:
            self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            self.logger.warning(f"⚠️ Elemento no encontrado: {selector}")
            return False

    def hacer_click(self, selector: str):
        """Hace click en un elemento."""
        try:
            self.page.click(selector, timeout=5000)
        except Exception as e:
            self.logger.error(f"❌ Error al hacer click en {selector}: {e}")

    def escribir_texto(self, selector: str, texto: str):
        """Escribe texto en un input."""
        try:
            self.page.fill(selector, texto)
        except Exception as e:
            self.logger.error(f"❌ Error al escribir en {selector}: {e}")

    def obtener_texto_pagina(self) -> str:
        """Obtiene todo el texto visible de la página."""
        return self.page.inner_text("body")

    def obtener_elementos(self, selector: str):
        """Obtiene una lista de elementos que coinciden con el selector."""
        return self.page.locator(selector)

    def scroll_al_final(self):
        """Hace scroll hasta el final de la página."""
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    def cerrar_navegador(self):
        """Cierra el navegador de forma segura."""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            self.logger.info("🔒 Navegador Playwright cerrado")
        except Exception as e:
            self.logger.error(f"❌ Error al cerrar navegador: {e}")
