"""
Módulo: scrapers/indeed_scraper.py
Async unificado. No crea loops adicionales.
"""
import asyncio
import random
import urllib.parse
from typing import Optional, Callable, List
from loguru import logger
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright_stealth import stealth_async


class IndeedScraperPlaywright:
    def __init__(self):
        self.plataforma = "Indeed"
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._playwright = None

    async def iniciar_navegador(self, headless: bool = True):
        logger.info("🚀 Indeed: Iniciando Chromium async...")
        self._playwright = await async_playwright().start()

        self.browser = await self._playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.0.36",
            locale="es-PE"
        )

        self.page = await self.context.new_page()
        await stealth_async(self.page)
        logger.info("✅ Indeed: Navegador listo")

    async def _pausa_humana(self, min_s: float = 1.5, max_s: float = 3.5):
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def recolectar_ofertas(
        self,
        limite_ofertas: Optional[int] = 20,
        puesto: str = "",
        lugar: str = "",
        filtro_relevancia_cb: Optional[Callable] = None
    ) -> List[dict]:
        if not self.page:
            await self.iniciar_navegador()

        ofertas = []
        puesto_q = urllib.parse.quote(puesto)
        lugar_q = urllib.parse.quote(lugar)
        url = f"https://pe.indeed.com/jobs?q={puesto_q}&l={lugar_q}"

        logger.info(f"🚀 Indeed: {url}")
        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self._pausa_humana(3.0, 5.0)

        try:
            await self.page.wait_for_selector("div.job_seen_beacon, div[data-jk]", timeout=15000)
        except Exception:
            logger.warning("⚠️ Indeed: tarjetas no detectadas")

        pagina = 1
        while limite_ofertas is None or len(ofertas) < limite_ofertas:
            selectores = ["div.job_seen_beacon", "div[data-jk]", "li.css-5lfssg", "div.slider_container"]
            tarjetas = []
            for sel in selectores:
                tarjetas = await self.page.locator(sel).all()
                if tarjetas:
                    break

            if not tarjetas:
                logger.info("🏁 Indeed: sin más tarjetas")
                break

            for tarjeta in tarjetas:
                if limite_ofertas and len(ofertas) >= limite_ofertas:
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

                    texto = ""
                    for sel in ["#jobDescriptionText", ".jobsearch-JobComponent-description", "div.jobsearch-jobDescriptionText"]:
                        try:
                            elem = self.page.locator(sel).first
                            if await elem.count() > 0:
                                t = await elem.inner_text(timeout=4000)
                                if t and len(t.strip()) > 80:
                                    texto = t.strip()[:2000]
                                    break
                        except Exception:
                            continue

                    if not texto:
                        continue

                    titulo = puesto
                    try:
                        tit_elem = self.page.locator("h2[data-testid='jobsearch-JobInfoHeader-title'], h1.jobsearch-JobInfoHeader-title, h2.jobTitle").first
                        titulo = (await tit_elem.inner_text(timeout=2500)).strip()
                    except Exception:
                        pass

                    empresa = "No especificada"
                    try:
                        emp_elem = self.page.locator("div[data-testid='jobsearch-CompanyInfoContainer'], a[href*='/cmp/']").first
                        if await emp_elem.count() > 0:
                            empresa = (await emp_elem.inner_text(timeout=2000)).strip().split("\n")[0]
                    except Exception:
                        pass

                    if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                        continue

                    ofertas.append({
                        "link_oferta": link_oferta,
                        "plataforma_origen": self.plataforma,
                        "texto_crudo": texto,
                        "titulo_puesto": titulo,
                        "empresa_extraida": empresa
                    })
                    logger.info(f"📦 Indeed [{len(ofertas)}] {titulo[:55]}")

                except Exception as e:
                    logger.debug(f"Indeed error tarjeta: {e}")

            # Paginación
            try:
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                pausa = random.uniform(5.0, 8.0) if pagina < 4 else random.uniform(10.0, 18.0)
                await asyncio.sleep(pausa)

                next_btn = self.page.locator("a[data-testid='pagination-page-next'], a[aria-label*='Next'], a[aria-label*='Siguiente']")
                if await next_btn.count() == 0:
                    break
                disabled = await next_btn.get_attribute("aria-disabled")
                if disabled == "true":
                    break

                await next_btn.click()
                pagina += 1
                await self._pausa_humana(3.5, 5.5)
            except Exception as e:
                logger.info(f"🏁 Indeed fin paginación: {e}")
                break

        logger.info(f"✅ Indeed: {len(ofertas)} ofertas")
        return ofertas

    async def cerrar_navegador(self):
        if self.browser:
            await self.browser.close()
            logger.info("🔒 Indeed: navegador cerrado")
        if self._playwright:
            await self._playwright.stop()

    def recolectar_ofertas_sync(self, **kwargs):
        return asyncio.run(self.recolectar_ofertas(**kwargs))

    def cerrar_navegador_sync(self):
        asyncio.run(self.cerrar_navegador())
