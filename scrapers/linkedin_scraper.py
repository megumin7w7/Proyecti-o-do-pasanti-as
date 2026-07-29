"""
Módulo: scrapers/linkedin_scraper.py (Optimizado para velocidad - Sin abrir cada oferta)
"""
import time
import urllib.parse
from scrapers.base_scraper import BaseScraper
from loguru import logger

class LinkedInScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.plataforma = "LinkedIn"
        logger.info("✅ LinkedInScraper (Playwright) inicializado")

    def _destruir_modales(self):
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
        if not self.page:
            self.iniciar_navegador(headless=True)
            
        ofertas_recopiladas = []
        puesto_url = urllib.parse.quote(puesto)
        lugar_url = urllib.parse.quote(lugar)
        offset = 0
        paginas_revisadas = 0
        max_paginas = 5  # Mantenemos 5 páginas pero más rápido
        
        try:
            while len(ofertas_recopiladas) < limite_ofertas and paginas_revisadas < max_paginas:
                url_busqueda = f"https://www.linkedin.com/jobs/search/?keywords={puesto_url}&location={lugar_url}&start={offset}"
                logger.info(f"🔍 LinkedIn (Pág {paginas_revisadas + 1}): {url_busqueda}")
                
                self.navegar_a(url_busqueda)
                time.sleep(1)  # ⚡ REDUCIDO de 3s a 1s
                self._destruir_modales()
                
                self.scroll_al_final()
                time.sleep(0.5)  # ⚡ REDUCIDO de 2s a 0.5s
                
                tarjetas = self.obtener_elementos("div.base-card, div.job-search-card, li.jobs-search-results__list-item")
                count = tarjetas.count()
                
                if count == 0:
                    logger.warning("⚠️ No hay tarjetas en esta página")
                    break
                
                logger.info(f"📦 {count} tarjetas encontradas")
                
                # ⚡ PROCESAMIENTO RÁPIDO: Extraer de la tarjeta sin abrir cada oferta
                for i in range(min(count, limite_ofertas - len(ofertas_recopiladas))):
                    try:
                        tarjeta = tarjetas.nth(i)
                        
                        # Extraer datos DIRECTAMENTE de la tarjeta (sin abrir)
                        try:
                            enlace = tarjeta.locator("a.base-card__full-link, a").first
                            href = enlace.get_attribute("href")
                            titulo = enlace.inner_text().strip()
                        except:
                            continue
                        
                        if not href or "job" not in href.lower():
                            continue
                        
                        # Verificar duplicados
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        
                        # Filtro de relevancia
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            continue
                        
                        #  EXTRACCIÓN RÁPIDA: Obtener texto de la tarjeta misma
                        # En lugar de abrir cada oferta, extraemos lo que podemos ver
                        try:
                            # Buscar descripción en la tarjeta
                            desc_elem = tarjeta.locator(".job-card-container__overflow, .job-card-list__description")
                            descripcion_corta = desc_elem.inner_text() if desc_elem.count() > 0 else ""
                            
                            # Buscar empresa
                            empresa_elem = tarjeta.locator(".job-card-container__company-name, h4")
                            empresa = empresa_elem.inner_text() if empresa_elem.count() > 0 else "No especificada"
                            
                            # Construir texto crudo con lo disponible
                            texto_crudo = f"{titulo}\n{empresa}\n{descripcion_corta}"
                        except:
                            texto_crudo = titulo
                        
                        # ⚡ Solo abrir la oferta si el texto es muy corto (< 100 chars)
                        if len(texto_crudo) < 150:
                            logger.debug(f"🔍 Texto corto, abriendo oferta completa...")
                            self.page.evaluate(f"window.open('{href}', '_blank')")
                            self.page.wait_for_timeout(500)  # ⚡ REDUCIDO
                            
                            self.page = self.page.context.pages[-1]
                            time.sleep(1)  #  REDUCIDO de 3s a 1s
                            self._destruir_modales()
                            
                            try:
                                btn_ver_mas = self.page.locator("button.show-more-less-html__button").first
                                btn_ver_mas.click()
                                time.sleep(0.5)  # ⚡ REDUCIDO
                            except:
                                pass
                            
                            try:
                                cuerpo = self.page.locator("main, section.core-rail").first
                                texto_crudo = cuerpo.inner_text()[:2000]
                            except:
                                texto_crudo = self.obtener_texto_pagina()[:2000]
                            
                            self.page.close()
                            self.page = self.page.context.pages[0]
                        
                        # Guardar oferta
                        if texto_crudo and len(texto_crudo) > 100:
                            ofertas_recopiladas.append({
                                "link_oferta": href,
                                "plataforma_origen": self.plataforma,
                                "texto_crudo": texto_crudo,
                                "titulo_puesto": titulo
                            })
                            logger.debug(f"✅ [{len(ofertas_recopiladas)}] {titulo[:40]}...")
                        
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
