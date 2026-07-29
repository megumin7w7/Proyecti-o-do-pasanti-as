"""
Módulo: scrapers/bumeran_scraper.py (Corregido y Optimizado para Playwright)
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
                # ✅ MANTENER LA UBICACIÓN EN TODAS LAS PÁGINAS DE BÚSQUEDA
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
                
                # Buscar enlaces de ofertas
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
                        
                        # ✅ EXTRACCIÓN ROBUSTA DEL TÍTULO
                        titulo = ""
                        try:
                            # Buscar elemento h2, h3 o clase de título dentro de la tarjeta
                            titulo_el = enlace.locator("h2, h3, [class*='title'], [class*='Title']").first
                            if titulo_el.count() > 0:
                                titulo = titulo_el.inner_text().strip()
                        except Exception:
                            pass

                        # Fallback: Extraer filtrando etiquetas comunes (Destacado, Urgente, etc.)
                        if not titulo:
                            texto_tarjeta = enlace.inner_text()
                            lineas = [l.strip() for l in texto_tarjeta.split('\n') if l.strip() and len(l.strip()) > 3]
                            lineas_filtradas = [
                                l for l in lineas 
                                if not any(bad in l.lower() for bad in ["destacado", "hace ", "urgente", "nuevo", "publicado", "días", "ayer", "hoy"])
                            ]
                            titulo = lineas_filtradas[0] if lineas_filtradas else (lineas[0] if lineas else "")

                        if not titulo:
                            continue

                        # 1. Verificar duplicados
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            logger.info(f"⏭️ Descartado (Duplicado): {titulo[:30]}")
                            continue
                            
                        # 2. Filtro de relevancia
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            logger.info(f"⏭️ Descartado (No relevante): '{titulo}' vs '{puesto}'")
                            continue
                        
                        # ✅ NAVEGACIÓN SEGURA A LA OFERTA
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
                            
                            # 3. Validar longitud del texto
                            if texto_crudo and len(texto_crudo) > 150:
                                ofertas_recopiladas.append({
                                    "link_oferta": href,
                                    "plataforma_origen": self.plataforma,
                                    "texto_crudo": texto_crudo[:2000],
                                    "titulo_puesto": titulo
                                })
                                logger.info(f"✅ [{len(ofertas_recopiladas)}] Guardada: {titulo[:35]}...")
                            else:
                                logger.warning(f"⚠️ Descartado (Texto muy corto < 150 chars): {titulo[:30]}")
                        finally:
                            # Garantiza que la pestaña siempre se cierre sin afectar la página principal
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
