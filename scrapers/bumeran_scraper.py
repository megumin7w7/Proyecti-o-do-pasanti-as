"""
Módulo: scrapers/bumeran_scraper.py (Corregido: Extracción limpia de títulos)
"""
import re
import time
from scrapers.base_scraper import BaseScraper
from loguru import logger

class BumeranScraper(BaseScraper):
    """Scraper específico para Bumeran usando Playwright"""
    def __init__(self):
        super().__init__()
        self.plataforma = "Bumeran"
        logger.info("✅ BumeranScraper (Playwright) inicializado")

    def _destruir_modales(self, target_page=None):
        """Elimina modales con JavaScript."""
        page_to_use = target_page or self.page
        try:
            page_to_use.evaluate("""
                document.querySelectorAll('[class*="banner"], [id*="cookie"], [class*="modal"]').forEach(e => e.remove());
                document.body.style.overflow = 'auto';
            """)
        except Exception:
            pass

    def _extraer_titulo_limpio(self, enlace_element) -> str:
        """Extrae el título real ignorando metadatos como 'Actualizado hace X días'"""
        # Patron Regex para detectar cualquier texto de metadatos/fecha/estado
        patron_ruido = r'actualizad[oa]|hace|d[ií]as?|ayer|hoy|publicad[oa]|urgente|destacad[oa]|nuevo|empleos'

        # Intentar 1: Buscar por etiquetas HTML típicas de título
        for selector in ["h2", "h3", "h1", "[class*='Title']", "[class*='title']"]:
            try:
                el = enlace_element.locator(selector).first
                if el.count() > 0:
                    texto = el.inner_text().strip()
                    if texto and not re.search(patron_ruido, texto, re.IGNORECASE):
                        return texto
            except Exception:
                pass

        # Intentar 2: Recorrer las líneas de texto de la tarjeta y filtrar ruido
        try:
            texto_tarjeta = enlace_element.inner_text()
            lineas = [l.strip() for l in texto_tarjeta.split('\n') if l.strip()]
            for linea in lineas:
                # Si la línea tiene más de 3 letras y NO contiene palabras de ruido
                if len(linea) > 3 and not re.search(patron_ruido, linea, re.IGNORECASE):
                    return linea
        except Exception:
            pass

        return ""
    def recolectar_ofertas(self, url_semilla: str = "", limite_ofertas: int = 20, 
                          puesto: str = "analista de datos", lugar: str = "lima", 
                          filtro_relevancia_cb=None) -> list:
        if not self.page: self.iniciar_navegador(headless=True)
            
        ofertas_recopiladas = []
        puesto_slug = puesto.lower().replace(" ", "-")
        lugar_slug = lugar.lower().replace(" ", "-") if lugar else ""
        pagina_actual = 1
        
        try:
            while len(ofertas_recopiladas) < limite_ofertas:
                if lugar_slug and pagina_actual == 1:
                    url_busqueda = f"https://www.bumeran.com.pe/en-{lugar_slug}/empleos-busqueda-{puesto_slug}.html"
                else:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html"
                
                if pagina_actual > 1:
                    conector = "&" if "?" in url_busqueda else "?"
                    url_busqueda = f"{url_busqueda}{conector}page={pagina_actual}"
                    
                logger.info(f"🔍 Bumeran (Pág {pagina_actual}): {url_busqueda}")
                self.navegar_a(url_busqueda)
                time.sleep(1.5) # ⚡ REDUCIDO de 3s a 1.5s
                self._destruir_modales()
                
                self.scroll_al_final()
                time.sleep(1) # ⚡ REDUCIDO de 2s a 1s
                
                enlaces = self.obtener_elementos("a[href*='-aviso-'], a[href*='/empleos/']")
                count = enlaces.count()
                if count == 0:
                    logger.warning(f"⚠️ No hay ofertas en página {pagina_actual}")
                    break
                
                logger.info(f"📦 {count} enlaces encontrados")
                
                for i in range(min(count, limite_ofertas - len(ofertas_recopiladas))):
                    try:
                        enlace = enlaces.nth(i)
                        href = enlace.get_attribute("href")
                        if href and not href.startswith("http"): href = f"https://www.bumeran.com.pe{href}"
                        if not href or "busqueda" in href: continue
                        
                        texto_tarjeta = enlace.inner_text()
                        lineas = [l.strip() for l in texto_tarjeta.split('\n') if l.strip() and len(l.strip()) > 3]
                        if not lineas: continue
                        titulo = lineas[0]
                        
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas): continue
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto): continue
                        
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                        self.page.wait_for_timeout(500) # ⚡ REDUCIDO
                        
                        self.page = self.page.context.pages[-1]
                        time.sleep(1) # ⚡ REDUCIDO de 2s a 1s
                        self._destruir_modales()
                        
                        try:
                            cuerpo = self.page.locator("main, section, div.job-description").first
                            texto_crudo = cuerpo.inner_text()
                        except:
                            texto_crudo = self.page.inner_text("body")
                        
                        if texto_crudo and len(texto_crudo) > 150:
                            ofertas_recopiladas.append({"link_oferta": href, "plataforma_origen": self.plataforma, "texto_crudo": texto_crudo[:2000], "titulo_puesto": titulo})
                            logger.debug(f"✅ [{len(ofertas_recopiladas)}] {titulo[:35]}...")
                        
                        self.page.close()
                        self.page = self.page.context.pages[0]
                    except Exception as e:
                        logger.error(f"❌ Error en oferta {i}: {e}")
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                pagina_actual += 1
                if pagina_actual > 5: break # Límite de seguridad
        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas")
        return ofertas_recopiladas
