"""
Módulo: scrapers/bumeran_scraper.py (Migrado a Playwright)
"""
import time
from scrapers.base_scraper import BaseScraper
from loguru import logger

class BumeranScraper(BaseScraper):
    """Scraper específico para Bumeran usando Playwright"""
    def __init__(self):
        super().__init__()
        self.plataforma = "Bumeran"
        logger.info("✅ BumeranScraper (Playwright) inicializado")

    def _destruir_modales(self):
        """Elimina modales con JavaScript."""
        try:
            self.page.evaluate("""
                document.querySelectorAll('[class*="banner"], [id*="cookie"], [class*="modal"]').forEach(e => e.remove());
                document.body.style.overflow = 'auto';
            """)
        except Exception:
            pass

    def recolectar_ofertas(self, url_semilla: str = "", limite_ofertas: int = 20, 
                          puesto: str = "analista de datos", lugar: str = "lima", 
                          filtro_relevancia_cb=None) -> list:
        """Recolecta ofertas de Bumeran."""
        if not self.page:
            self.iniciar_navegador(headless=True)
            
        ofertas_recopiladas = []
        puesto_slug = puesto.lower().replace(" ", "-")
        pagina_actual = 1
        
        try:
            while len(ofertas_recopiladas) < limite_ofertas:
                if pagina_actual == 1:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html"
                    logger.info(f"🔍 Bumeran (Pág 1): {url_busqueda}")
                    
                    self.navegar_a(url_busqueda)
                    time.sleep(3)
                    self._destruir_modales()
                    
                    # Aplicar filtro de ubicación si existe
                    if lugar:
                        try:
                            input_lugar = self.page.locator("input[aria-label='Lugar de trabajo']").first
                            input_lugar.fill(lugar.capitalize())
                            self.page.keyboard.press("Enter")
                            time.sleep(3)
                            logger.info(f"📍 Filtro de ubicación aplicado: {lugar}")
                        except Exception as e:
                            logger.warning(f"️ No se pudo aplicar filtro de ubicación: {e}")
                else:
                    # Paginación via URL
                    try:
                        url_actual = self.page.url
                        import re
                        if "page=" in url_actual:
                            nueva_url = re.sub(r'([?&])page=\d+', rf'\g<1>page={pagina_actual}', url_actual)
                        else:
                            conector = "&" if "?" in url_actual else "?"
                            nueva_url = f"{url_actual}{conector}page={pagina_actual}"
                        
                        self.navegar_a(nueva_url)
                        time.sleep(3)
                        self._destruir_modales()
                    except Exception as e:
                        logger.error(f"🏁 Error en paginación: {e}")
                        break
                
                # Scroll para cargar contenido
                self.scroll_al_final()
                time.sleep(2)
                
                # Buscar enlaces de ofertas
                enlaces = self.obtener_elementos("a[href*='-aviso-'], a[href*='/empleos/']")
                count = enlaces.count()
                
                if count == 0:
                    logger.warning(f"️ No hay ofertas en página {pagina_actual}")
                    break
                
                logger.info(f" {count} enlaces encontrados")
                
                # Procesar ofertas
                for i in range(min(count, limite_ofertas - len(ofertas_recopiladas))):
                    try:
                        enlace = enlaces.nth(i)
                        href = enlace.get_attribute("href")
                        
                        # ✅ FIX: Completar URL si es relativa
                        if href and not href.startswith("http"):
                            href = f"https://www.bumeran.com.pe{href}"
                        
                        texto_tarjeta = enlace.inner_text()
                        if not href or "busqueda" in href:
                            continue
                        
                        # Limpiar título
                        lineas = [l.strip() for l in texto_tarjeta.split('\n') if l.strip()]
                        if not lineas:
                            continue
                        
                        titulo = lineas[0]
                        
                        # Verificar duplicados y filtro
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            continue
                        
                        # Abrir oferta
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                        self.page.wait_for_timeout(1000)
                        
                        # Cambiar a nueva pestaña
                        self.page = self.page.context.pages[-1]
                        time.sleep(2)
                        self._destruir_modales()
                        
                        # ✅ FIX: Extraer solo el contenedor principal
                        try:
                            cuerpo = self.page.locator("main, section, div.job-description").first
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
                            logger.debug(f"✅ [{len(ofertas_recopiladas)}] {titulo[:35]}...")
                        
                        # Cerrar y volver
                        self.page.close()
                        self.page = self.page.context.pages[0]
                        
                    except Exception as e:
                        logger.error(f"❌ Error en oferta {i}: {e}")
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                pagina_actual += 1
                
        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas")
        return ofertas_recopiladas
