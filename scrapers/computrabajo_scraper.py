"""
Módulo: scrapers/computrabajo_scraper.py
"""
import time
from typing import Optional, Callable, List
from loguru import logger
from scrapers.base_scraper import BaseScraper


class ComputrabajoScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.plataforma = "Computrabajo"

    def _eliminar_obstaculos(self):
        try:
            self.page.evaluate("""
                document.querySelectorAll('[class*="modal"], [id*="cookie"], button[class*="close"]').forEach(e => {
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
        pagina = 1
        max_paginas = 30

        puesto_q = puesto.lower().replace(" ", "-") if puesto else ""
        lugar_q = lugar.lower().replace(" ", "-") if lugar else ""

        if puesto_q and lugar_q:
            url_base = f"https://pe.computrabajo.com/trabajo-de-{puesto_q}-en-{lugar_q}"
        elif puesto_q:
            url_base = f"https://pe.computrabajo.com/trabajo-de-{puesto_q}"
        else:
            logger.error("Computrabajo: falta puesto")
            return []

        while pagina <= max_paginas and len(ofertas) < limite_ofertas:
            url = f"{url_base}?p={pagina}"
            logger.info(f"📄 Computrabajo Página {pagina}")

            if not self.navegar_a(url):
                break

            time.sleep(1.5)
            self._eliminar_obstaculos()

            enlaces = self.obtener_elementos("a.js-o-link")
            count = enlaces.count()
            if count == 0:
                logger.info("🏁 Fin de resultados en Computrabajo")
                break

            for i in range(min(count, limite_ofertas - len(ofertas))):
                try:
                    elem = enlaces.nth(i)
                    href = elem.get_attribute("href")
                    titulo = elem.inner_text().strip()
                    if not href or not titulo:
                        continue
                    if not href.startswith("http"):
                        href = f"https://pe.computrabajo.com{href}"
                    if any(o["link_oferta"] == href for o in ofertas):
                        continue
                    if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                        continue

                    empresa = "No especificada"
                    try:
                        card = elem.locator("xpath=ancestor::article[1]")
                        empresa_elem = card.locator("[class*='company'], [class*='empresa'], [class*='nombre']").first
                        if empresa_elem.count() > 0:
                            empresa = empresa_elem.inner_text().strip()
                    except Exception:
                        pass

                    with self.context.expect_page(timeout=10000) as info:
                        self.page.evaluate(f"window.open('{href}', '_blank')")

                    nueva = info.value
                    try:
                        nueva.wait_for_load_state("domcontentloaded", timeout=5000)
                        try:
                            cuerpo = nueva.locator("main, section.job-description, div.offer_requirements, .job-description").first
                            texto = cuerpo.inner_text(timeout=3000)[:4000]
                        except Exception:
                            texto = nueva.inner_text("body", timeout=3000)[:4000]

                        if texto and len(texto) > 50:
                            ofertas.append({
                                "link_oferta": href,
                                "plataforma_origen": self.plataforma,
                                "texto_crudo": texto,
                                "titulo_puesto": titulo,
                                "empresa_extraida": empresa
                            })
                            logger.debug(f"✅ [{len(ofertas)}] {titulo[:40]}")
                    except Exception as e:
                        logger.debug(f"Error detalle: {e}")
                    finally:
                        if not nueva.is_closed():
                            nueva.close()

                except Exception as e:
                    logger.debug(f"Error tarjeta {i}: {e}")

            pagina += 1

        logger.info(f"✅ Computrabajo: {len(ofertas)} ofertas")
        return ofertas
