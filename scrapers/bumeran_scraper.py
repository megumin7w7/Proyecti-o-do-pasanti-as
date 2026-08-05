"""
Módulo: scrapers/bumeran_scraper.py
"""
from typing import Optional, Callable, List
from loguru import logger
from scrapers.base_scraper import BaseScraper
from utils.url_cleaner import normalizar_termino_busqueda


class BumeranScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.plataforma = "Bumeran"

    def _destruir_modales(self):
        try:
            self.page.evaluate("""
                document.querySelectorAll('[class*="modal"], [class*="Popup"], button[class*="close"], div[id*="dfp"]').forEach(e => {
                    if (e.offsetParent !== null) e.click();
                });
            """)
        except Exception:
            pass

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
        slug = normalizar_termino_busqueda(puesto)["slug_guiones"]

        for pagina in range(1, 10):
            if len(ofertas) >= limite_ofertas:
                break

            url = (f"https://www.bumeran.com.pe/empleos-busqueda-{slug}.html?page={pagina}"
                   if pagina > 1 else
                   f"https://www.bumeran.com.pe/empleos-busqueda-{slug}.html")

            logger.info(f"📄 Bumeran Página {pagina}")

            if not self.navegar_a(url, wait_until="domcontentloaded"):
                break

            self._destruir_modales()

            try:
                self.page.wait_for_selector("a[href*='/empleos/']", timeout=10000)
            except Exception:
                logger.warning("⚠️ No se detectaron ofertas en Bumeran")
                break

            enlaces = self.page.locator("a[href*='/empleos/']").all()
            if not enlaces:
                break

            for enlace in enlaces:
                if len(ofertas) >= limite_ofertas:
                    break

                try:
                    href = enlace.get_attribute("href")
                    titulo = enlace.inner_text().strip() or puesto
                    if not href:
                        continue
                    if not href.startswith("http"):
                        href = f"https://www.bumeran.com.pe{href}"
                    if any(o["link_oferta"] == href for o in ofertas):
                        continue
                    if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                        continue

                    empresa = "No especificada"
                    try:
                        card = enlace.locator("xpath=ancestor::article[1] | xpath=ancestor::div[contains(@class,'card')][1]")
                        emp = card.locator("[class*='company'], [class*='empresa']").first
                        if emp.count() > 0:
                            empresa = emp.inner_text().strip()
                    except Exception:
                        pass

                    with self.context.expect_page(timeout=10000) as info:
                        self.page.evaluate(f"window.open('{href}', '_blank')")

                    nueva = info.value
                    try:
                        nueva.wait_for_load_state("domcontentloaded", timeout=5000)
                        try:
                            cuerpo = nueva.locator("[id*='aviso-description'], [class*='aviso-description'], div[class*='Description']").first
                            texto = cuerpo.inner_text(timeout=2000)[:3000]
                        except Exception:
                            texto = nueva.inner_text("body", timeout=2000)[:3000]

                        if texto and len(texto) > 50:
                            ofertas.append({
                                "link_oferta": href,
                                "plataforma_origen": self.plataforma,
                                "texto_crudo": texto,
                                "titulo_puesto": titulo.split('\n')[0],
                                "empresa_extraida": empresa
                            })
                    except Exception as e:
                        logger.debug(f"Error detalle Bumeran: {e}")
                    finally:
                        if not nueva.is_closed():
                            nueva.close()

                except Exception as e:
                    logger.debug(f"Error enlace Bumeran: {e}")

        logger.info(f"✅ Bumeran: {len(ofertas)} ofertas")
        return ofertas
