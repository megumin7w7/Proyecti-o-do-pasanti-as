import asyncio
import random
import time
import urllib.parse
from typing import List, Optional, Callable
from loguru import logger
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

class IndeedScraperPlaywright:
    """Scraper de Indeed Perú usando Playwright + stealth (Optimizado para Linux/HF)"""
    
    def __init__(self):
        self.plataforma = "Indeed"
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        logger.info("✅ IndeedScraperPlaywright inicializado")

    async def iniciar_navegador(self, headless: bool = True):
        """
        Lanza Chromium usando el motor nativo de Playwright.
        Compatible con Linux (Hugging Face) y Windows local.
        """
        logger.info("🚀 Iniciando Chromium con Playwright...")
        playwright = await async_playwright().start()
        
        # Lanzamos el navegador. En HF siempre será headless=True
        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        
        # Creamos un contexto "limpio" (sin perfil persistente para evitar bloqueos por huella digital)
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            locale='es-PE'
        )
        
        # Inyectar scripts para evadir detección de bots (Stealth básico)
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)
        
        self.page = await self.context.new_page()
        logger.success("✅ Navegador Playwright listo y configurado para HF/Linux")

    async def _pausa_humana(self, min_seg: float = 1.5, max_seg: float = 3.5):
        await asyncio.sleep(random.uniform(min_seg, max_seg))

    async def _esperar_captcha(self, timeout: int = 50) -> bool:
        """Detecta y espera resolución de Cloudflare Turnstile"""
        try:
            indicadores = [
                "text=Verifique que es un ser humano",
                "text=Verificación adicional requerida",
                "iframe[src*='challenges.cloudflare.com']",
                "iframe[src*='turnstile']"
            ]
            captcha_detectado = False
            for selector in indicadores:
                try:
                    if await self.page.locator(selector).count() > 0:
                        captcha_detectado = True
                        break
                except Exception:
                    continue

            if not captcha_detectado:
                return True

            logger.warning("🛡️ CAPTCHA Cloudflare detectado. Esperando...")
            
            # En HF no podemos resolverlo manualmente, así que esperamos o reintentamos
            inicio = time.time()
            while time.time() - inicio < timeout:
                await asyncio.sleep(3.0)
                content = await self.page.content()
                content_lower = content.lower()
                if any(x in content_lower for x in ["¡operación exitosa!", "success", "verificado"]):
                    logger.success("✅ Cloudflare superado")
                    return True
                if "verifique que es un ser humano" not in content_lower:
                    logger.success("✅ Cloudflare desapareció")
                    return True
                    
            logger.warning("⚠️ Timeout de Cloudflare. Es posible que la IP de HF esté bloqueada.")
            return False
        except Exception as e:
            logger.debug(f"Error en espera captcha: {e}")
            return True

    async def recolectar_ofertas(
        self,
        puesto: str = "analista de datos",
        lugar: str = "lima",
        limite_ofertas: Optional[int] = None,
        filtro_relevancia_cb: Optional[Callable] = None
    ) -> List[dict]:
        if not self.page:
            await self.iniciar_navegador(headless=True) # Forzamos headless en HF

        ofertas = []
        puesto_q = urllib.parse.quote(puesto)
        lugar_q = urllib.parse.quote(lugar)
        url = f"https://pe.indeed.com/jobs?q={puesto_q}&l={lugar_q}"
        
        logger.info(f"🚀 Navegando a: {url}")
        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self._pausa_humana(3.0, 5.0)
        
        await self._esperar_captcha(timeout=60)

        try:
            await self.page.wait_for_selector("div.job_seen_beacon, div.jobsearch-ResultsList, div[data-jk]", timeout=15000)
            logger.success("✅ Tarjetas detectadas en el DOM")
        except Exception:
            logger.warning("⚠️ No se detectaron tarjetas rápidamente. Continuando...")

        pagina = 1
        modo_ilimitado = limite_ofertas is None or limite_ofertas <= 0
        
        while modo_ilimitado or len(ofertas) < limite_ofertas:
            await self._esperar_captcha()
            
            selectores_tarjeta = [
                "div.job_seen_beacon", "div[data-jk]", "li.css-5lfssg", 
                "div.jobsearch-ResultsList > div", "div.slider_container"
            ]
            tarjetas = []
            for sel in selectores_tarjeta:
                tarjetas = await self.page.locator(sel).all()
                if tarjetas:
                    logger.info(f"📄 Página {pagina}: {len(tarjetas)} tarjetas con selector '{sel}'")
                    break

            if not tarjetas:
                logger.info("🏁 No hay más ofertas o la página está vacía.")
                break

            for idx, tarjeta in enumerate(tarjetas, 1):
                if not modo_ilimitado and len(ofertas) >= limite_ofertas:
                    break
                try:
                    data_jk = await tarjeta.get_attribute("data-jk")
                    if not data_jk:
                        try:
                            link = tarjeta.locator("a[data-jk], a[href*='jk=']").first
                            href = await link.get_attribute("href")
                            if href and "jk=" in href:
                                data_jk = href.split("jk=")[-1].split("&")[0]
                        except Exception:
                            continue
                    if not data_jk:
                        continue

                    link_oferta = f"https://pe.indeed.com/viewjob?jk={data_jk}"
                    if any(o["link_oferta"] == link_oferta for o in ofertas):
                        continue

                    try:
                        await tarjeta.scroll_into_view_if_needed(timeout=4000)
                    except Exception:
                        pass
                    await self._pausa_humana(0.4, 0.8)
                    
                    try:
                        await tarjeta.click(timeout=3000)
                    except Exception:
                        try:
                            await tarjeta.locator("a").first.click(timeout=2500)
                        except Exception:
                            continue
                    await self._pausa_humana(1.5, 2.5)

                    # === EXTRACCIÓN DE DESCRIPCIÓN ===
                    texto_crudo = ""
                    selectores_desc = [
                        "#jobDescriptionText", ".jobsearch-JobComponent-description",
                        "div.jobsearch-jobDescriptionText", "div[id*='jobDescription']"
                    ]
                    for sel in selectores_desc:
                        try:
                            elem = self.page.locator(sel).first
                            if await elem.count() > 0:
                                texto = await elem.inner_text(timeout=4000)
                                if texto and len(texto.strip()) > 80:
                                    texto_crudo = texto.strip()
                                    break
                        except Exception:
                            continue

                    if not texto_crudo:
                        continue

                    titulo = puesto
                    try:
                        titulo_elem = self.page.locator("h2[data-testid='jobsearch-JobInfoHeader-title'], h1.jobsearch-JobInfoHeader-title, h2.jobTitle").first
                        titulo = (await titulo_elem.inner_text(timeout=2500)).strip()
                    except Exception:
                        pass

                    if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                        continue

                    ofertas.append({
                        "link_oferta": link_oferta,
                        "plataforma_origen": self.plataforma,
                        "texto_crudo": texto_crudo,
                        "titulo_puesto": titulo
                    })
                    logger.info(f"📦 [{len(ofertas)}] {titulo[:55]}...")
                except Exception as e:
                    logger.debug(f"Error tarjeta {idx}: {e}")
                    continue

            # Paginación
            try:
                logger.info(f"➡️ Intentando página {pagina + 1}...")
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                pausa = random.uniform(5.0, 8.0) if pagina < 4 else random.uniform(10.0, 18.0)
                await asyncio.sleep(pausa)
                
                next_btn = self.page.locator("a[data-testid='pagination-page-next'], a[aria-label*='Next'], a[aria-label*='Siguiente']")
                if await next_btn.count() == 0 or await next_btn.get_attribute("aria-disabled") == "true":
                    logger.info("🏁 Última página alcanzada")
                    break
                await next_btn.click()
                pagina += 1
                await self._pausa_humana(3.5, 5.5)
            except Exception as e:
                logger.info(f"🏁 Fin de paginación: {e}")
                break

        logger.info(f"🎉 Total extraído Indeed: {len(ofertas)} ofertas")
        return ofertas

    def recolectar_ofertas_sync(self, **kwargs):
        """Versión síncrona para usar desde main.py o Streamlit"""
        return asyncio.run(self.recolectar_ofertas(**kwargs))

    async def cerrar(self):
        if self.browser:
            await self.browser.close()
            logger.info(" Navegador Playwright cerrado")

    def cerrar_navegador(self):
        """Compatible con main.py síncrono"""
        if self.browser:
            try:
                asyncio.run(self.cerrar())
            except Exception:
                pass