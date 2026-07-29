"""
Módulo: scrapers/computrabajo_scraper.py (Migrado a Playwright)
"""
import time
from scrapers.base_scraper import BaseScraper
from loguru import logger

class ComputrabajoScraper(BaseScraper):
    """Scraper específico para Computrabajo usando Playwright"""
    def __init__(self):
        super().__init__()
        self.plataforma = "Computrabajo"
        logger.info("✅ ComputrabajoScraper (Playwright) inicializado")

    def _eliminar_obstaculos(self):
        """Cierra modales y cookies con JavaScript."""
        try:
            self.page.evaluate("""
                document.querySelectorAll('[class*="modal"], [id*="cookie"], button[class*="close"]').forEach(e => {
                    if (e.offsetParent !== null) e.click();
                });
            """)
            logger.debug("🛡️ Modales eliminados")
        except Exception:
            pass

    def recolectar_ofertas(self, url_semilla: str = "", limite_ofertas: int = 20, 
                          puesto: str = None, lugar: str = None, filtro_relevancia_cb=None) -> list:
        """Recolecta ofertas de Computrabajo usando paginación dinámica."""
        if not self.page:
            self.iniciar_navegador(headless=True)
            
        ofertas_recopiladas = []
        pagina_actual = 1
        MAX_PAGINAS = 30
        
        puesto_query = puesto.lower().replace(" ", "-") if puesto else ""
        lugar_query = lugar.lower().replace(" ", "-") if lugar else ""
        
        if puesto_query and lugar_query:
            url_base = f"https://pe.computrabajo.com/trabajo-de-{puesto_query}-en-{lugar_query}"
        elif puesto_query:
            url_base = f"https://pe.computrabajo.com/trabajo-de-{puesto_query}"
        else:
            url_base = url_semilla.rstrip('/')
        
        try:
            while pagina_actual <= MAX_PAGINAS and len(ofertas_recopiladas) < limite_ofertas:
                url_pagina = f"{url_base}?p={pagina_actual}"
                logger.info(f"📄 Página {pagina_actual}: {url_pagina}")
                self.navegar_a(url_pagina)
                time.sleep(2)
                self._eliminar_obstaculos()
                
                ofertas_locator = self.obtener_elementos("a.js-o-link")
                count = ofertas_locator.count()
                
                if count == 0:
                    logger.warning(f"🏁 No hay más ofertas en página {pagina_actual}")
                    break
                
                logger.info(f"📦 {count} ofertas encontradas en página {pagina_actual}")
                
                for i in range(min(count, limite_ofertas - len(ofertas_recopiladas))):
                    try:
                        oferta_elem = ofertas_locator.nth(i)
                        href = oferta_elem.get_attribute("href")
                        titulo = oferta_elem.inner_text().strip()
                        
                        if not href or not titulo:
                            continue
                        
                        # ✅ 1. ASEGURAR URL ABSOLUTA
                        if not href.startswith("http"):
                            href = f"https://pe.computrabajo.com{href}"
                        
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            continue
                        
                        # Abrir oferta en nueva pestaña
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                        self.page.wait_for_timeout(1000)
                        
                        # Cambiar a la nueva pestaña
                        self.page = self.page.context.pages[-1]
                        time.sleep(1.5)
                        
                        # ✅ 2. CAPTURAR DESCRIPCIÓN COMPLETA (hasta 4000 chars)
                        try:
                            cuerpo = self.page.locator("main, section.job-description, div.offer_requirements, .job-description").first
                            texto_crudo = cuerpo.inner_text()[:4000]
                        except:
                            texto_crudo = self.page.inner_text("body")[:4000]
                        
                        if texto_crudo and len(texto_crudo) > 50:
                            ofertas_recopiladas.append({
                                "link_oferta": href,  # ✅ URL ABSOLUTA
                                "plataforma_origen": self.plataforma,
                                "texto_crudo": texto_crudo,  # ✅ DESCRIPCIÓN COMPLETA
                                "titulo_puesto": titulo
                            })
                            logger.debug(f"✅ [{len(ofertas_recopiladas)}] {titulo[:40]}...")
                        
                        # Cerrar pestaña y volver al listado
                        self.page.close()
                        self.page = self.page.context.pages[0]
                        
                    except Exception as e:
                        logger.error(f"❌ Error procesando oferta {i}: {e}")
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                            
                pagina_actual += 1
                
        except Exception as e:
            logger.error(f"❌ Error crítico en scraping: {e}")
        
        logger.info(f"✅ Total extraído: {len(ofertas_recopiladas)} ofertas")
        return ofertas_recopiladas
