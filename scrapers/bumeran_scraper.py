"""
Módulo: scrapers/bumeran_scraper.py (Versión Blindada para Playwright)
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
        if not self.page:
            self.iniciar_navegador(headless=True)
            
        ofertas_recopiladas = []
        puesto_slug = puesto.lower().replace(" ", "-")
        lugar_slug = lugar.lower().replace(" ", "-") if lugar else ""
        pagina_actual = 1
        
        try:
            while len(ofertas_recopiladas) < limite_ofertas:
                # Estrategia de URL: Intentar con ubicación, si no, sin ubicación
                if lugar_slug and pagina_actual == 1:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}-en-{lugar_slug}.html"
                else:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html"
                
                if pagina_actual > 1:
                    conector = "&" if "?" in url_busqueda else "?"
                    url_busqueda = f"{url_busqueda}{conector}page={pagina_actual}"
                    
                logger.info(f"🔍 Bumeran (Pág {pagina_actual}): {url_busqueda}")
                self.navegar_a(url_busqueda)
                time.sleep(3)
                self._destruir_modales()
                
                # 🛡️ DETECTOR DE CAPTCHA: Si Bumeran nos bloquea, salimos limpiamente
                page_content = self.page.inner_text("body").lower()
                if "verifica que eres un humano" in page_content or "cloudflare" in page_content or "acceso denegado" in page_content:
                    logger.warning("🛡️ Bumeran detectó comportamiento de bot (CAPTCHA). Saltando portal...")
                    break
                
                self.scroll_al_final()
                time.sleep(2)
                
                # ✅ SELECTOR INFALIBLE: Buscar TODOS los enlaces y filtrar en memoria
                enlaces = self.obtener_elementos("a")
                count_total = enlaces.count()
                
                enlaces_ofertas = []
                for i in range(count_total):
                    try:
                        enlace = enlaces.nth(i)
                        href = enlace.get_attribute("href")
                        # Filtramos manualmente por patrones conocidos de Bumeran
                        if href and ("/aviso/" in href or "-aviso-" in href) and "busqueda" not in href:
                            texto_tarjeta = enlace.inner_text()
                            if texto_tarjeta and len(texto_tarjeta.strip()) > 10:
                                enlaces_ofertas.append((href, texto_tarjeta.strip()))
                    except:
                        continue
                
                # Eliminar duplicados manteniendo el orden
                seen = set()
                enlaces_unicos = []
                for href, texto in enlaces_ofertas:
                    if href not in seen:
                        seen.add(href)
                        enlaces_unicos.append((href, texto))
                
                count = len(enlaces_unicos)
                
                if count == 0:
                    logger.warning(f"⚠️ No se encontraron enlaces de ofertas válidos en página {pagina_actual}.")
                    break
                
                logger.info(f"📦 {count} enlaces de ofertas únicos encontrados")
                
                # Procesar ofertas
                for href, texto_tarjeta in enlaces_unicos:
                    if len(ofertas_recopiladas) >= limite_ofertas:
                        break
                    
                    # Limpiar título (la primera línea no vacía suele ser el título)
                    lineas = [l.strip() for l in texto_tarjeta.split('\n') if l.strip() and len(l.strip()) > 3]
                    if not lineas:
                        continue
                    titulo = lineas[0]
                    
                    if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                        continue
                    if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                        continue
                    
                    try:
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                        self.page.wait_for_timeout(1500)
                        
                        # Cambiar a nueva pestaña
                        self.page = self.page.context.pages[-1]
                        time.sleep(2)
                        self._destruir_modales()
                        
                        # Extraer texto
                        try:
                            cuerpo = self.page.locator("main, section, div.job-description, div.offer-content").first
                            texto_crudo = cuerpo.inner_text()
                        except:
                            texto_crudo = self.page.inner_text("body")
                        
                        texto_crudo = re.sub(r'\n\s*\n', '\n', texto_crudo).strip()
                        
                        if texto_crudo and len(texto_crudo) > 150:
                            ofertas_recopiladas.append({
                                "link_oferta": href,
                                "plataforma_origen": self.plataforma,
                                "texto_crudo": texto_crudo[:2000],
                                "titulo_puesto": titulo
                            })
                            logger.debug(f"✅ [{len(ofertas_recopiladas)}] {titulo[:35]}...")
                        else:
                            logger.debug(f"⚠️ Descartado (texto corto/bloqueado): {titulo[:30]}")
                        
                        # Cerrar y volver
                        self.page.close()
                        self.page = self.page.context.pages[0]
                        
                    except Exception as e:
                        logger.error(f"❌ Error en oferta: {e}")
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                pagina_actual += 1
                if pagina_actual > 10: # Límite de seguridad
                    logger.info("🏁 Límite de 10 páginas alcanzado para Bumeran.")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error crítico en Bumeran: {e}")
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas con éxito")
        return ofertas_recopiladas
