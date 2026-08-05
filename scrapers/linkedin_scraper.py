"""
Módulo: scrapers/linkedin_scraper.py
Scroll infinito con detección de altura estable + extracción de empresa.
"""
from typing import Optional, Callable, List
from loguru import logger
from scrapers.base_scraper import BaseScraper
from utils.url_cleaner import normalizar_termino_busqueda


class LinkedInScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.plataforma = "LinkedIn"

    def recolectar_ofertas(
        self,
        limite_ofertas: int = 20,
        puesto: str = "",
        lugar: str = "",
        filtro_relevancia_cb: Optional[Callable] = None
    ) -> List[dict]:
        if not self.page:
            self.iniciar_navegador()

        ofertas = []
        q_puesto = normalizar_termino_busqueda(puesto)["slug_mas"]
        q_lugar = normalizar_termino_busqueda(lugar)["slug_mas"]

        url = f"https://pe.linkedin.com/jobs/search?keywords={q_puesto}&location={q_lugar}&f_TPR=r2592000"
        logger.info(f"🚀 LinkedIn: {url}")

        if not self.navegar_a(url, wait_until="domcontentloaded"):
            return ofertas

        altura_previa = 0
        intentos_sin_cambio = 0
        while intentos_sin_cambio < 5:
            self.scroll_al_final()
            self.page.wait_for_timeout(1200)
            altura = self.page.evaluate("document.body.scrollHeight")
            if altura == altura_previa:
                intentos_sin_cambio += 1
            else:
                intentos_sin_cambio = 0
                altura_previa = altura

        tarjetas = self.page.locator("a.base-card__full-link, a.job-search-card__title").all()
        pendientes = []

        for tarjeta in tarjetas:
            if len(pendientes) >= limite_ofertas * 2:
                break
            try:
                href = tarjeta.get_attribute("href")
                titulo = tarjeta.inner_text().strip()
                if not href:
                    continue
                href = href.split('?')[0]
                if not any(p["link"] == href for p in pendientes):
                    pendientes.append({"link": href, "titulo": titulo})
            except Exception:
                continue

        logger.info(f"🔗 LinkedIn: {len(pendientes)} enlaces")

        for item in pendientes[:limite_ofertas]:
            href = item["link"]
            titulo = item["titulo"]

            try:
                self.page.goto(href, wait_until="domcontentloaded", timeout=12000)
                try:
                    self.page.evaluate("""
                        document.querySelectorAll('button.modal__dismiss, button.sign-in-modal__dismiss').forEach(b => b.click());
                    """)
                except Exception:
                    pass

                if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                    continue

                empresa = "No especificada"
                try:
                    emp_sel = self.page.locator("a.topcard__org-name-link, span.topcard__flavor, a[href*='/company/']").first
                    if emp_sel.count() > 0:
                        empresa = emp_sel.inner_text().strip()
                except Exception:
                    pass

                try:
                    desc = self.page.locator("div.show-more-less-html__markup, div.description__text").first
                    texto = desc.inner_text(timeout=4000)[:3000]
                except Exception:
                    texto = self.page.inner_text("body", timeout=3000)[:3000]

                if texto and len(texto) > 50:
                    ofertas.append({
                        "link_oferta": href,
                        "plataforma_origen": self.plataforma,
                        "texto_crudo": texto,
                        "titulo_puesto": titulo,
                        "empresa_extraida": empresa
                    })
                    logger.debug(f"✅ LinkedIn: {titulo[:40]}")

            except Exception as e:
                logger.debug(f"LinkedIn timeout: {e}")

        logger.info(f"✅ LinkedIn: {len(ofertas)} ofertas")
        return ofertas
