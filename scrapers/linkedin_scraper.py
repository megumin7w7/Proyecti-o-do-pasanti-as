"""
Módulo: scrapers/linkedin_scraper.py (Migrado a Playwright)
"""
import time
import urllib.parse
from scrapers.base_scraper import BaseScraper
from loguru import logger

class LinkedInScraper(BaseScraper):
    """Scraper específico para LinkedIn usando Playwright"""
    def __init__(self):
        super().__init__()
        self.plataforma = "LinkedIn"
        logger.info("✅ LinkedInScraper (Playwright) inicializado")

    def _destruir_modales(self):
        """Elimina modales de login."""
        try:
            self.page.evaluate("""
                document.querySelectorAll('[role="dialog"], .modal, .contextual-sign-in-modal').forEach(e => e.remove());
                document.body.style.overflow = 'auto';
            """)
        except Exception:
            pass

    def recolectar_ofertas(self, url_semilla: str = "", limite_ofertas: int = 20, 
                          puesto: str = "practicante", lugar: str = "peru", 
                          filtro_relevancia_cb=None) -> list:
        """Recolecta ofertas de LinkedIn."""
        if not self.page:
            self.iniciar_navegador(headless=True)
            
        ofertas_recopiladas = []
        puesto_url = urllib.parse.quote(puesto)
        lugar_url = urllib.parse.quote(lugar)
        offset = 0
        paginas_revisadas = 0
        max_paginas = 5
        
        try:
            while len(ofertas_recopiladas) < limite_ofertas and paginas_revisadas < max_paginas:
                url_busqueda = f"https://www.linkedin.com/jobs/search/?keywords={puesto_url}&location={lugar_url}&start={offset}"
                logger.info(f"🔍 LinkedIn (Pág {paginas_revisadas + 1}): {url_busqueda}")
                
                self.navegar_a(url_busqueda)
                time.sleep(3)
                self._destruir_modales()
                
                # Scroll
                self.scroll_al_final()
                time.sleep(2)
                
                # Buscar tarjetas
                tarjetas = self.obtener_elementos("div.base-card, div.job-search-card, li.jobs-search-results__list-item")
                count = tarjetas.count()
                
                if count == 0:
                    logger.warning("⚠️ No hay tarjetas en esta página")
                    break
                
                logger.info(f"📦 {count} tarjetas encontradas")
                
                # Procesar tarjetas
                for i in range(min(count, limite_ofertas - len(ofertas_recopiladas))):
                    try:
                        tarjeta = tarjetas.nth(i)
                        
                        # Obtener enlace
                        try:
                            enlace = tarjeta.locator("a.base-card__full-link, a").first
                            href = enlace.get_attribute("href")
                            titulo = enlace.inner_text().strip()
                        except:
                            continue
                        
                        # ✅ FIX: Completar URL si es relativa
                        if href and not href.startswith("http"):
                            href = f"https://www.linkedin.com{href}"
                        
                        if not href or "job" not in href.lower():
                            continue
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            continue
                        
                        # Abrir oferta
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                        self.page.wait_for_timeout(1000)
                        
                        # Cambiar a nueva pestaña
                        self.page = self.page.context.pages[-1]
                        time.sleep(3)
                        self._destruir_modales()
                        
                        # Click en "Ver más"
                        try:
                            btn_ver_mas = self.page.locator("button.show-more-less-html__button").first
                            btn_ver_mas.click()
                            time.sleep(1.5)
                        except:
                            pass
                        
                        # ✅ FIX: Extraer solo el contenedor principal
                        try:
                            cuerpo = self.page.locator("main, section.core-rail").first
                            texto_crudo = cuerpo.inner_text()[:2000]
                        except:
                            texto_crudo = self.obtener_texto_pagina()[:2000]
                        
                        if texto_crudo and len(texto_crudo) > 100:
                            ofertas_recopiladas.append({
                                "link_oferta": href,
                                "plataforma_origen": self.plataforma,
                                "texto_crudo": texto_crudo,
                                "titulo_puesto": titulo
                            })
                            logger.debug(f"✅ [{len(ofertas_recopiladas)}] {titulo[:40]}...")
                        
                        # Cerrar y volver
                        self.page.close()
                        self.page = self.page.context.pages[0]
                        
                    except Exception as e:
                        logger.error(f"❌ Error en tarjeta {i}: {e}")
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                offset += 25
                paginas_revisadas += 1
                
        except Exception as e:
            logger.error(f"❌ Error crítico LinkedIn: {e}")
        
        logger.info(f"✅ Total LinkedIn: {len(ofertas_recopiladas)} ofertas")
        return ofertas_recopiladas
