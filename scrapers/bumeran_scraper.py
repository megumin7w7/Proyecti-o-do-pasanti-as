"""
Módulo: scrapers/bumeran_scraper.py (Corregido con selectores universales)
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
                # Construir URL correcta
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
                
                # 🕵️ DEBUG: Imprimir todos los enlaces que encontramos para diagnóstico
                todos_los_enlaces = self.obtener_elementos("a")
                logger.debug(f"🔍 Total de enlaces <a> en la página: {todos_los_enlaces.count()}")
                
                # Imprimir los primeros 10 hrefs para ver el patrón
                for i in range(min(10, todos_los_enlaces.count())):
                    try:
                        href = todos_los_enlaces.nth(i).get_attribute("href")
                        if href and "http" in href:
                            logger.debug(f"   Link {i}: {href[:100]}")
                    except:
                        pass
                
                # ✅ ESTRATEGIA 1: Buscar por clases de tarjetas de empleo (más confiable)
                selectores_posibles = [
                    "a[href*='/empleo/']",           # Patrón moderno: /empleo/xxx
                    "a[href*='/empleos/']",          # Patrón alternativo
                    ".job-card a",                   # Tarjetas con clase job-card
                    ".offer-card a",                 # Tarjetas con clase offer-card  
                    "[class*='job'] a",              # Cualquier clase que contenga 'job'
                    "[class*='offer'] a",            # Cualquier clase que contenga 'offer'
                    "a[href]",                       # Cualquier enlace (fallback)
                ]
                
                enlaces = None
                for selector in selectores_posibles:
                    try:
                        enlaces = self.obtener_elementos(selector)
                        count = enlaces.count()
                        if count > 0:
                            logger.info(f"✅ Selector '{selector}' encontró {count} enlaces")
                            break
                    except:
                        continue
                
                if not enlaces or enlaces.count() == 0:
                    logger.warning(f"⚠️ No se encontraron enlaces con ningún selector en página {pagina_actual}")
                    break
                
                # Filtrar solo los que parecen ofertas reales (no footer, no navegación)
                enlaces_filtrados = []
                for i in range(enlaces.count()):
                    try:
                        enlace = enlaces.nth(i)
                        href = enlace.get_attribute("href")
                        texto = enlace.inner_text().strip()
                        
                        # Filtrar enlaces que NO son de ofertas
                        if not href:
                            continue
                        if "busqueda" in href or "login" in href or "registro" in href:
                            continue
                        if len(texto) < 10:  # Enlaces muy cortos suelen ser iconos o navegación
                            continue
                        if any(x in href.lower() for x in [".com.pe/", "bumeran.com"]):
                            # Es un enlace interno válido
                            enlaces_filtrados.append((enlace, href, texto))
                    except:
                        continue
                
                logger.info(f" {len(enlaces_filtrados)} enlaces de ofertas válidos encontrados")
                
                if len(enlaces_filtrados) == 0:
                    logger.warning(f"⚠️ No hay ofertas válidas en página {pagina_actual}")
                    break
                
                # Procesar ofertas
                for enlace, href, texto_tarjeta in enlaces_filtrados:
                    if len(ofertas_recopiladas) >= limite_ofertas:
                        break
                    
                    try:
                        # Completar URL si es relativa
                        if href and not href.startswith("http"):
                            href = f"https://www.bumeran.com.pe{href}"
                        
                        # Limpiar título (primera línea no vacía)
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
                        logger.debug(f" Abriendo: {titulo[:40]}...")
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                        self.page.wait_for_timeout(1000)
                        
                        # Cambiar a nueva pestaña
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
                        
                        # Validar que tenga contenido suficiente
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
                        
                        # Cerrar y volver
                        self.page.close()
                        self.page = self.page.context.pages[0]
                        
                    except Exception as e:
                        logger.error(f"❌ Error en oferta: {e}")
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                pagina_actual += 1
                if pagina_actual > 5:
                    logger.info("🏁 Límite de 5 páginas alcanzado.")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error crítico en Bumeran: {e}")
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas con éxito")
        return ofertas_recopiladas
