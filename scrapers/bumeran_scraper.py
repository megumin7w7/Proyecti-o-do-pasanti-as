"""
Módulo: scrapers/bumeran_scraper.py (Optimizado para GitHub Actions / Headless)
"""
import time
import re
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
                document.querySelectorAll('[class*="banner"], [id*="cookie"], [class*="modal"], [class*="overlay"]').forEach(e => e.remove());
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
        lugar_slug = lugar.lower().replace(" ", "-") if lugar else ""
        pagina_actual = 1
        
        try:
            while len(ofertas_recopiladas) < limite_ofertas:
                # ✅ MEJORA 1: Construir URL con ubicación desde el inicio (más estable que escribir en inputs)
                if lugar_slug:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}-en-{lugar_slug}.html"
                else:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html"
                
                # Si es página > 1, agregar el parámetro de paginación
                if pagina_actual > 1:
                    conector = "&" if "?" in url_busqueda else "?"
                    url_busqueda = f"{url_busqueda}{conector}page={pagina_actual}"
                    
                logger.info(f"🔍 Bumeran (Pág {pagina_actual}): {url_busqueda}")
                self.navegar_a(url_busqueda)
                time.sleep(3)
                self._destruir_modales()
                
                # Scroll para cargar contenido dinámico
                self.scroll_al_final()
                time.sleep(2)
                
                # ✅ MEJORA 2: Selector más estricto para evitar enlaces de footer/publicidad
                enlaces = self.obtener_elementos("a[href*='-aviso-']")
                count = enlaces.count()
                
                if count == 0:
                    logger.warning(f"⚠️ No hay ofertas en página {pagina_actual}")
                    break
                
                logger.info(f"📦 {count} enlaces de ofertas encontrados")
                
                # Procesar ofertas
                for i in range(min(count, limite_ofertas - len(ofertas_recopiladas))):
                    try:
                        enlace = enlaces.nth(i)
                        href = enlace.get_attribute("href")
                        
                        # Completar URL si es relativa
                        if href and not href.startswith("http"):
                            href = f"https://www.bumeran.com.pe{href}"
                        
                        if not href or "busqueda" in href:
                            continue
                        
                        # Obtener título de la tarjeta
                        texto_tarjeta = enlace.inner_text()
                        lineas = [l.strip() for l in texto_tarjeta.split('\n') if l.strip() and len(l.strip()) > 3]
                        if not lineas:
                            continue
                        
                        titulo = lineas[0]
                        
                        # Verificar duplicados y filtro de relevancia
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            continue
                        
                        # Abrir oferta en nueva pestaña
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                        self.page.wait_for_timeout(1500)
                        
                        # Cambiar a nueva pestaña
                        self.page = self.page.context.pages[-1]
                        time.sleep(2)
                        self._destruir_modales()
                        
                        # ✅ MEJORA 3: Extracción de texto más robusta
                        try:
                            # Intentar agarrar el contenedor principal de la oferta
                            cuerpo = self.page.locator("main, section, div.job-description, div.offer-content").first
                            texto_crudo = cuerpo.inner_text()
                        except:
                            # Fallback al body completo
                            texto_crudo = self.page.inner_text("body")
                        
                        # Limpieza básica de espacios múltiples
                        texto_crudo = re.sub(r'\n\s*\n', '\n', texto_crudo).strip()
                        
                        if texto_crudo and len(texto_crudo) > 150: # Umbral un poco más alto para evitar páginas de error
                            ofertas_recopiladas.append({
                                "link_oferta": href,
                                "plataforma_origen": self.plataforma,
                                "texto_crudo": texto_crudo[:2000], # Limitado a 2000 chars
                                "titulo_puesto": titulo
                            })
                            logger.debug(f"✅ [{len(ofertas_recopiladas)}] {titulo[:35]}...")
                        else:
                            logger.debug(f"⚠️ Descartado (texto muy corto o bloqueado): {titulo[:30]}")
                        
                        # Cerrar pestaña y volver al listado
                        self.page.close()
                        self.page = self.page.context.pages[0]
                        
                    except Exception as e:
                        logger.error(f"❌ Error en oferta {i}: {e}")
                        # Asegurar retorno a la pestaña principal
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                pagina_actual += 1
                if pagina_actual > 10: # Límite de seguridad para no scrapear infinitamente si algo falla
                    logger.info("🏁 Límite de 10 páginas alcanzado para Bumeran.")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error crítico en Bumeran: {e}")
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas con éxito")
        return ofertas_recopiladas
