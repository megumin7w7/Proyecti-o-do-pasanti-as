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
        """Recolecta ofertas de Bumeran con extracción limpia y manejo seguro de pestañas."""
        if not self.page:
            self.iniciar_navegador(headless=True)
            
        ofertas_recopiladas = []
        puesto_slug = puesto.lower().replace(" ", "-")
        lugar_slug = lugar.lower().replace(" ", "-") if lugar else ""
        pagina_actual = 1
        
        try:
            while len(ofertas_recopiladas) < limite_ofertas:
                if lugar_slug:
                    base_url = f"https://www.bumeran.com.pe/en-{lugar_slug}/empleos-busqueda-{puesto_slug}.html"
                else:
                    base_url = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html"
                
                url_busqueda = base_url if pagina_actual == 1 else f"{base_url}?page={pagina_actual}"
                    
                logger.info(f"🔍 Bumeran (Pág {pagina_actual}): {url_busqueda}")
                self.navegar_a(url_busqueda)
                time.sleep(3)
                self._destruir_modales()
                
                self.scroll_al_final()
                time.sleep(2)
                
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
                        
                        if href and not href.startswith("http"):
                            href = f"https://www.bumeran.com.pe{href}"
                        
                        if not href or "busqueda" in href:
                            continue
                        
                        # Extraer título real filtrando fechas y etiquetas
                        titulo = self._extraer_titulo_limpio(enlace)

                        if not titulo:
                            logger.warning(f"⚠️ No se pudo determinar el título en la oferta {i}")
                            continue

                        # 1. Verificar duplicados
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            logger.info(f"⏭️ Descartado (Duplicado): {titulo[:30]}")
                            continue
                            
                        # 2. Filtro de relevancia
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            logger.info(f"⏭️ Descartado (No relevante): '{titulo}' vs '{puesto}'")
                            continue
                        
                        # Navegación a la oferta en nueva pestaña
                        detalle_page = self.page.context.new_page()
                        try:
                            detalle_page.goto(href, timeout=20000, wait_until="domcontentloaded")
                            time.sleep(1.5)
                            self._destruir_modales(detalle_page)
                            
                            try:
                                cuerpo = detalle_page.locator("main, section, div.job-description, div[class*='description']").first
                                texto_crudo = cuerpo.inner_text()
                            except Exception:
                                texto_crudo = detalle_page.inner_text("body")
                            
                            texto_crudo = re.sub(r'\n\s*\n', '\n', texto_crudo).strip()
                            
                            if texto_crudo and len(texto_crudo) > 150:
                                ofertas_recopiladas.append({
                                    "link_oferta": href,
                                    "plataforma_origen": self.plataforma,
                                    "texto_crudo": texto_crudo[:2000],
                                    "titulo_puesto": titulo
                                })
                                logger.info(f"✅ [{len(ofertas_recopiladas)}] Guardada: {titulo[:35]}...")
                            else:
                                logger.warning(f"⚠️ Descartado (Texto corto < 150 chars): {titulo[:30]}")
                        finally:
                            detalle_page.close()
                        
                    except Exception as e:
                        logger.error(f"❌ Error en oferta {i}: {e}")
                
                pagina_actual += 1
                if pagina_actual > 5:
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error crítico en Bumeran: {e}")
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas")
        return ofertas_recopiladas
