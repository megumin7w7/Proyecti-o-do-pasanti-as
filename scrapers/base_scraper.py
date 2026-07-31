"""
Módulo: scrapers/base_scraper.py (Optimizado para CI/CD + Stealth + Aceleración de Red)
"""
import time
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from playwright_stealth import stealth_sync
from loguru import logger

class BaseScraper:
    """Clase base de alto rendimiento para scrapers de Playwright."""
    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.logger = logger

    def iniciar_navegador(self, headless: bool = True):
        """Inicializa Chromium con evasión de anti-bots y aceleración de red."""
        self.logger.info("🌐 Inicializando Chromium (Stealth + Resource Blocker)...")
        self.playwright = sync_playwright().start()
        
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security"
            ]
        )
        
        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="es-PE",
            timezone_id="America/Lima"
        )
        
        self.page = self.context.new_page()
        
        # 1. APLICAR STEALTH
        stealth_sync(self.page)
        
        # 2. BLOQUEO DE RECURSOS PESADOS (Súper Aceleración)
        def interceptar_rutas(route):
            request = route.request
            resource_type = request.resource_type
            # Si es imagen, fuente, media o analytics, lo abortamos para ahorrar ancho de banda
            if resource_type in ["image", "media", "font"] or "analytics" in request.url or "doubleclick" in request.url:
                route.abort()
            else:
                route.continue_()
                
        self.page.route("**/*", interceptar_rutas)
        
        # 3. MASKING ADICIONAL
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)
        
        self.logger.info("✅ Navegador base iniciado y optimizado")
        return self.page

    def navegar_a(self, url: str, wait_until: str = "commit", timeout: int = 40000) -> bool:
        """Navega a una URL evitando bloqueos por timeout de red."""
        try:
            self.logger.debug(f"🔗 Navegando a: {url[:80]}...")
            self.page.goto(url, wait_until=wait_until, timeout=timeout)
            self.page.wait_for_timeout(800)  # Pausa no bloqueante recomendada por Playwright
            return True
        except Exception as e:
            self.logger.warning(f"⚠️ Alerta de navegación en {url[:50]}: {e}")
            try:
                self.page.reload(wait_until="commit", timeout=20000)
                return True
            except Exception:
                return False

    def obtener_elementos(self, selector: str):
        return self.page.locator(selector)

    def scroll_al_final(self):
        try:
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass

    def debug_snapshot(self, nombre="debug"):
        """Guarda evidencia para GitHub Actions si ocurre un fallo."""
        try:
            if self.page:
                self.page.screenshot(path=f"{nombre}.png", full_page=True)
                with open(f"{nombre}.html", "w", encoding="utf-8") as f:
                    f.write(self.page.content())
                self.logger.warning(f"📸 Debug guardado: {nombre}.png / {nombre}.html")
        except Exception as e:
            self.logger.error(f"No se pudo guardar snapshot: {e}")

    def cerrar_navegador(self):
        """Cierra de forma limpia los procesos."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            self.logger.info("🔒 Navegador cerrado correctamente")
        except Exception as e:
            self.logger.error(f"❌ Error al cerrar navegador: {e}")
