"""
Módulo: scrapers/bumeran_scraper.py (Con Diagnóstico de Fallos)
"""
import time
import re
from scrapers.base_scraper import BaseScraper
from loguru import logger

class BumeranScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.plataforma = "Bumeran"
        logger.info("✅ BumeranScraper (Playwright) inicializado")

    def _destruir_modales(self):
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
        if not self.page:
            self.iniciar_navegador(headless=True)
            
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
                time.sleep(1.5)
                self._destruir_modales()
                
                self.scroll_al_final()
                time.sleep(1)
                
                # Selector más estricto para evitar basura
                enlaces = self.obtener_elementos("a[href*='-aviso-']")
                count = enlaces.count()
                
                if count == 0:
                    logger.warning(f"⚠️ No hay enlaces '-aviso-' en página {pagina_actual}")
                    break
                
                logger.info(f"📦 {count} enlaces potenciales encontrados")
                
                for i in range(min(count, limite_ofertas - len(ofertas_recopiladas))):
                    try:
                        enlace = enlaces.nth(i)
                        href = enlace.get_attribute("href")
                        if href and not href.startswith("http"):
                            href = f"https://www.bumeran.com.pe{href}"
                        
                        if not href or "busqueda" in href:
                            continue
                        
                        texto_tarjeta = enlace.inner_text()
                        lineas = [l.strip() for l in texto_tarjeta.split('\n') if l.strip() and len(l.strip()) > 3]
                        if not lineas:
                            continue
                        
                        titulo = lineas[0]
                        
                        # 🕵️ DIAGNÓSTICO 1: Filtro de relevancia
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            logger.debug(f"⏭️ Descartado por filtro: '{titulo}'")
                            continue
                        
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                        self.page.wait_for_timeout(1000)
                        
                        self.page = self.page.context.pages[-1]
                        time.sleep(1)
                        self._destruir_modales()
                        
                        try:
                            cuerpo = self.page.locator("main, section, div.job-description").first
                            texto_crudo = cuerpo.inner_text()
                        except:
                            texto_crudo = self.page.inner_text("body")
                        
                        texto_crudo = re.sub(r'\n\s*\n', '\n', texto_crudo).strip()
                        
                        # 🕵️ DIAGNÓSTICO 2: Longitud del texto (Bloqueo CAPTCHA)
                        if texto_crudo and len(texto_crudo) > 150:
                            ofertas_recopiladas.append({
                                "link_oferta": href,
                                "plataforma_origen": self.plataforma,
                                "texto_crudo": texto_crudo[:2000],
                                "titulo_puesto": titulo
                            })
                            logger.info(f"✅ [{len(ofertas_recopiladas)}] Guardada: {titulo[:35]}...")
                        else:
                            logger.warning(f"⚠️ Descartada por texto corto ({len(texto_crudo)} chars). Posible bloqueo: '{titulo[:30]}'")
                        
                        self.page.close()
                        self.page = self.page.context.pages[0]
                        
                    except Exception as e:
                        logger.error(f"❌ Error en oferta {i}: {e}")
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                pagina_actual += 1
                if pagina_actual > 5: 
                    logger.info("🏁 Límite de 5 páginas alcanzado para Bumeran.")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error crítico en Bumeran: {e}")
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas con éxito")
        return ofertas_recopiladas
