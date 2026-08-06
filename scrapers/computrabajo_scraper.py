"""
Módulo: scrapers/computrabajo_scraper.py (Migrado a Playwright)
"""
import time
from scrapers.base_scraper import BaseScraper
from loguru import logger
from utils.time_parser import calcular_dias_antiguedad

class ComputrabajoScraper(BaseScraper):
    """Scraper específico para Computrabajo usando Playwright"""
    def __init__(self):
        super().__init__()
        self.plataforma = "Computrabajo"
        logger.info("✅ ComputrabajoScraper (Playwright) inicializado")

    def _eliminar_obstaculos(self):
        """Cierra modales y cookies con JavaScript."""
        try:
            self.page.evaluate("""
                document.querySelectorAll('[class*="modal"], [id*="cookie"], button[class*="close"]').forEach(e => {
                    if (e.offsetParent !== null) e.click();
                });
            """)
            logger.debug("🛡️ Modales eliminados")
        except Exception:
            pass

    def recolectar_ofertas(self, url_semilla: str = "", limite_ofertas: int = 20, 
                          puesto: str = None, lugar: str = None, filtro_relevancia_cb=None,
                          urls_existentes: set = None) -> list:
        """Pipeline dividido: 1. Descubrimiento de URLs -> 2. Extracción secuencial."""
        if not self.page:
            self.iniciar_navegador(headless=False)
            
        if urls_existentes is None: 
            urls_existentes = set()
            
        ofertas_recopiladas = []
        enlaces_pendientes = []
        pagina_actual = 1
        MAX_PAGINAS = 30
        
        puesto_query = puesto.lower().replace(" ", "-") if puesto else ""
        lugar_query = lugar.lower().replace(" ", "-") if lugar else ""
        
        if puesto_query and lugar_query:
            url_base = f"https://pe.computrabajo.com/trabajo-de-{puesto_query}-en-{lugar_query}"
        elif puesto_query:
            url_base = f"https://pe.computrabajo.com/trabajo-de-{puesto_query}"
        else:
            url_base = url_semilla.rstrip('/')
            
        # ==========================================
        # FASE 1: DESCUBRIMIENTO DE ENLACES
        # ==========================================
        try:
            while pagina_actual <= MAX_PAGINAS and len(enlaces_pendientes) < limite_ofertas:
                url_pagina = f"{url_base}?p={pagina_actual}"
                self.logger.info(f"📄 Explorando Página {pagina_actual}: {url_pagina}")
                self.navegar_a(url_pagina)
                time.sleep(2)
                self._eliminar_obstaculos()
                
                ofertas_locator = self.obtener_elementos("a.js-o-link")
                count = ofertas_locator.count()
                
                if count == 0:
                    self.logger.warning(f"🏁 No hay más ofertas en página {pagina_actual}")
                    break
                
                for i in range(count):
                    if len(enlaces_pendientes) >= limite_ofertas: 
                        break
                    
                    try:
                        elem = ofertas_locator.nth(i)
                        href = elem.get_attribute("href")
                        titulo = elem.inner_text().strip()
                        
                        # 🚀 TRUCO: Subimos al 'article' padre para leer la fecha de la tarjeta completa
                        texto_tarjeta = elem.evaluate("el => el.closest('article') ? el.closest('article').innerText : el.innerText")
                        
                        # ⏳ FILTRO DE ANTIGÜEDAD AQUÍ
                        dias = calcular_dias_antiguedad(texto_tarjeta)
                        if dias > 45:
                            self.logger.debug(f"⏳ Descartada por vieja ({dias} días): {href}")
                            continue
                        
                        if not href or not titulo: 
                            continue
                            
                        if not href.startswith("http"): 
                            href = f"https://pe.computrabajo.com{href}"
                        
                        # === FILTRO DE MEMORIA COMPARTIDA ===
                        if href in urls_existentes: 
                            continue
                        
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto): 
                            continue
                            
                        if not any(e["link"] == href for e in enlaces_pendientes):
                            enlaces_pendientes.append({"link": href, "titulo": titulo})
                            urls_existentes.add(href) # Agregamos al Set global
                            
                    except Exception as e:
                        self.logger.debug(f"Error evaluando nodo de enlace: {e}")
                        continue
                        
                pagina_actual += 1
                
        except Exception as e:
            self.logger.error(f"❌ Error en fase de descubrimiento: {e}")

        self.logger.info(f"🔗 {len(enlaces_pendientes)} enlaces listos. Iniciando extracción secuencial...")
        # ==========================================
        # FASE 2: EXTRACCIÓN DE CONTENIDO (Ultra-rápida)
        # ==========================================
        for item in enlaces_pendientes:
            
            # 🛑 AQUÍ VA EL FRENO DE EMERGENCIA
            # Revisa cuántas ofertas llevamos ANTES de abrir la siguiente página
            if len(ofertas_recopiladas) >= limite_ofertas:
                self.logger.info(f"🎯 Límite de {limite_ofertas} ofertas alcanzado. Deteniendo extracción.")
                break
                
            href = item["link"]
            titulo = item["titulo"]
            
            try:
                # 🚀 OPTIMIZACIÓN 1: "commit" corta la espera apenas llega el esqueleto de la página.
                self.navegar_a(href, wait_until="commit", timeout=10000)
                
                # 🚀 OPTIMIZACIÓN 2: Eliminamos el sleep de 1000ms. 
                # Playwright es inteligente y usará este inner_text para esperar solo lo estrictamente necesario.
                try:
                    cuerpo = self.page.locator("main, section.job-description, div.offer_requirements, .job-description").first
                    texto_crudo = cuerpo.inner_text(timeout=2500)[:4000]
                except:
                    # Plan B rápido si no encuentra los selectores principales
                    texto_crudo = self.page.inner_text("body", timeout=2500)[:4000]
                
                if texto_crudo and len(texto_crudo) > 50:
                    ofertas_recopiladas.append({
                        "link_oferta": href,
                        "plataforma_origen": self.plataforma,
                        "texto_crudo": texto_crudo,
                        "titulo_puesto": titulo
                    })
                    self.logger.debug(f"✅ Extrayendo: {titulo[:40]}...")
                    
            except Exception as e:
                self.logger.error(f"❌ Error extrayendo {titulo[:20]}: {e}")
                
        self.logger.info(f"✅ Total extraído Computrabajo: {len(ofertas_recopiladas)} ofertas")
        return ofertas_recopiladas
