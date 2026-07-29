"""
Módulo: scrapers/bumeran_scraper.py (Con diagnóstico y selectores universales)
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
                # URL correcta con ubicación
                if lugar_slug and pagina_actual == 1:
                    url_busqueda = f"https://www.bumeran.com.pe/en-{lugar_slug}/empleos-busqueda-{puesto_slug}.html"
                else:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html"
                
                if pagina_actual > 1:
                    conector = "&" if "?" in url_busqueda else "?"
                    url_busqueda = f"{url_busqueda}{conector}page={pagina_actual}"
                    
                logger.info(f"🔍 Bumeran (Pág {pagina_actual}): {url_busqueda}")
                self.navegar_a(url_busqueda)
                time.sleep(2)
                self._destruir_modales()
                
                # 🕵️ DEBUG: Inspeccionar TODOS los enlaces para encontrar el patrón
                todos_links = self.obtener_elementos("a")
                logger.debug(f"🔍 Total enlaces <a> en página: {todos_links.count()}")
                
                # Imprimir primeros 20 hrefs para ver el patrón real
                for i in range(min(20, todos_links.count())):
                    try:
                        href = todos_links.nth(i).get_attribute("href")
                        texto = todos_links.nth(i).inner_text()[:50]
                        if href and "http" in href:
                            logger.debug(f"   Link {i}: {href[:80]} | Texto: '{texto}'")
                    except:
                        pass
                
                # ✅ ESTRATEGIA: Probar múltiples selectores hasta encontrar uno que funcione
                selectores_posibles = [
                    "a[href*='/empleo/']",           # Patrón moderno
                    "a[href*='/empleos/']",          # Alternativo
                    ".job-card a",                   # Por clase
                    ".offer-card a",
                    "[class*='job'] a",
                    "article a[href]",               # Artículos de ofertas
                    "div[data-qa='offer'] a",        # Data attributes
                ]
                
                enlaces = None
                selector_usado = ""
                for selector in selectores_posibles:
                    try:
                        enlaces = self.obtener_elementos(selector)
                        count = enlaces.count()
                        if count > 0:
                            selector_usado = selector
                            logger.info(f"✅ Selector '{selector}' encontró {count} enlaces")
                            break
                    except Exception as e:
                        logger.debug(f"Selector '{selector}' falló: {e}")
                        continue
                
                if not enlaces or enlaces.count() == 0:
                    logger.warning(f"⚠️ No se encontraron enlaces con NINGÚN selector en página {pagina_actual}")
                    # Guardar screenshot para debug
                    self.page.screenshot(path=f"bumeran_debug_p{pagina_actual}.png")
                    logger.info("📸 Screenshot guardado para diagnóstico")
                    break
                
                # Filtrar solo ofertas válidas
                enlaces_filtrados = []
                for i in range(enlaces.count()):
                    try:
                        enlace = enlaces.nth(i)
                        href = enlace.get_attribute("href")
                        texto = enlace.inner_text().strip()
                        
                        if not href:
                            continue
                        if "busqueda" in href or "login" in href or "registro" in href:
                            continue
                        if len(texto) < 15:  # Muy corto = probablemente no es oferta
                            continue
                        
                        # Completar URL si es relativa
                        if not href.startswith("http"):
                            href = f"https://www.bumeran.com.pe{href}"
                        
                        enlaces_filtrados.append((enlace, href, texto))
                    except:
                        continue
                
                logger.info(f"📦 {len(enlaces_filtrados)} ofertas válidas encontradas")
                
                if len(enlaces_filtrados) == 0:
                    logger.warning(f"⚠️ No hay ofertas válidas en página {pagina_actual}")
                    break
                
                # Procesar ofertas
                for enlace, href, texto_tarjeta in enlaces_filtrados:
                    if len(ofertas_recopiladas) >= limite_ofertas:
                        break
                    
                    try:
                        # Limpiar título
                        lineas = [l.strip() for l in texto_tarjeta.split('\n') if l.strip() and len(l.strip()) > 3]
                        if not lineas:
                            continue
                        titulo = lineas[0]
                        
                        # Verificar duplicados
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        
                        # Filtro de relevancia
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            logger.debug(f"️ Descartado por filtro: '{titulo}'")
                            continue
                        
                        # Abrir oferta
                        logger.debug(f"🔗 Abriendo: {titulo[:40]}...")
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                        self.page.wait_for_timeout(1000)
                        
                        self.page = self.page.context.pages[-1]
                        time.sleep(1.5)
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
                            logger.info(f"✅ [{len(ofertas_recopiladas)}] Guardada: {titulo[:35]}...")
                        else:
                            logger.warning(f"⚠️ Descartada (texto corto: {len(texto_crudo)} chars): {titulo[:30]}")
                            # Guardar screenshot de la oferta fallida
                            self.page.screenshot(path=f"bumeran_oferta_fallida.png")
                        
                        self.page.close()
                        self.page = self.page.context.pages[0]
                        
                    except Exception as e:
                        logger.error(f"❌ Error en oferta: {e}")
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                pagina_actual += 1
                if pagina_actual > 5:
                    logger.info(" Límite de 5 páginas alcanzado.")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error crítico en Bumeran: {e}")
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas con éxito")
        return ofertas_recopiladas
