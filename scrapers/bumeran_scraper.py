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
                
                # 🕵️ DIAGNÓSTICO: Verificar título y posible bloqueo
                page_title = self.page.title()
                logger.info(f"📄 Título de la página recibida: '{page_title}'")
                
                if "access denied" in page_title.lower() or "cloudflare" in page_title.lower() or "just a moment" in page_title.lower():
                    logger.error("🛡️ BLOQUEO DETECTADO: Bumeran bloqueó la IP del servidor (Cloudflare/Datadome).")
                    # Guardar evidencia
                    self.page.screenshot(path="bumeran_bloqueo.png")
                    logger.info("📸 Screenshot guardado como 'bumeran_bloqueo.png'")
                    break
                
                self.scroll_al_final()
                time.sleep(2)
                
                # Buscar TODOS los enlaces y filtrar
                enlaces = self.obtener_elementos("a")
                count_total = enlaces.count()
                
                enlaces_ofertas = []
                for i in range(count_total):
                    try:
                        enlace = enlaces.nth(i)
                        href = enlace.get_attribute("href")
                        if href and ("/aviso/" in href or "-aviso-" in href) and "busqueda" not in href:
                            texto_tarjeta = enlace.inner_text()
                            if texto_tarjeta and len(texto_tarjeta.strip()) > 10:
                                enlaces_ofertas.append((href, texto_tarjeta.strip()))
                    except:
                        continue
                
                seen = set()
                enlaces_unicos = [(h, t) for h, t in enlaces_ofertas if not (h in seen or seen.add(h))]
                count = len(enlaces_unicos)
                
                if count == 0:
                    logger.warning(f"⚠️ No se encontraron enlaces de ofertas válidos.")
                    # 🕵️ DIAGNÓSTICO: Guardar screenshot de la página vacía
                    self.page.screenshot(path="bumeran_vacia.png")
                    logger.info("📸 Screenshot de página vacía guardado como 'bumeran_vacia.png'")
                    
                    # Intentar imprimir los primeros 200 caracteres del body para ver qué hay
                    body_text = self.page.inner_text("body")[:200]
                    logger.debug(f"🔍 Fragmento del body: '{body_text}'")
                    break
                
                logger.info(f"📦 {count} enlaces de ofertas únicos encontrados")
                
                for href, texto_tarjeta in enlaces_unicos:
                    if len(ofertas_recopiladas) >= limite_ofertas:
                        break
                    
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
                        self.page = self.page.context.pages[-1]
                        time.sleep(2)
                        self._destruir_modales()
                        
                        try:
                            cuerpo = self.page.locator("main, section, div.job-description").first
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
                        
                        self.page.close()
                        self.page = self.page.context.pages[0]
                    except Exception as e:
                        logger.error(f"❌ Error en oferta: {e}")
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                pagina_actual += 1
                if pagina_actual > 5: 
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error crítico en Bumeran: {e}")
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas")
        return ofertas_recopiladas
