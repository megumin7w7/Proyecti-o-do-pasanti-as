"""
Módulo: scrapers/bumeran_scraper.py (Corrección de extracción de título)
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
                document.querySelectorAll('[class*="banner"], [id*="cookie"], [class*="modal"]').forEach(e => e.remove());
                document.body.style.overflow = 'auto';
            """)
        except Exception:
            pass

    def recolectar_ofertas(self, url_semilla: str = "", limite_ofertas: int = 20, 
                          puesto: str = "analista de datos", lugar: str = "lima", 
                          filtro_relevancia_cb=None) -> list:
        
        ofertas_recopiladas = []
        
        if not self.page:
            self.iniciar_navegador(headless=True)
            
        puesto_slug = puesto.lower().replace(" ", "-")
        pagina_actual = 1
        
        while len(ofertas_recopiladas) < limite_ofertas:
            try:
                if pagina_actual == 1:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html"
                else:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html?page={pagina_actual}"
                    
                logger.info(f"🔍 Bumeran (Pág {pagina_actual}): {url_busqueda}")
                
                self.page.goto(url_busqueda, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                self._destruir_modales()
                
                if lugar and pagina_actual == 1:
                    try:
                        input_lugar = self.page.locator("input[aria-label='Lugar de trabajo']").first
                        input_lugar.fill(lugar.capitalize())
                        self.page.keyboard.press("Enter")
                        self.page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info(f"📍 Filtro de ubicación aplicado: {lugar}")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo aplicar filtro de ubicación: {e}")
                
                self.scroll_al_final()
                time.sleep(1.5)
                
                selector_ofertas = "a[href*='-aviso-'], a[href*='/empleos/']"
                try:
                    self.page.wait_for_selector(selector_ofertas, timeout=8000)
                except Exception:
                    logger.info(f"🏁 Bumeran: Fin de paginación en página {pagina_actual}")
                    break
                
                enlaces = self.obtener_elementos(selector_ofertas)
                count = enlaces.count()
                
                if count == 0:
                    logger.info(f"🏁 Bumeran: Fin de paginación en página {pagina_actual} (count == 0)")
                    break
                
                logger.info(f"📦 {count} enlaces encontrados en página {pagina_actual}")
                
                # Procesar ofertas
                for i in range(min(count, limite_ofertas - len(ofertas_recopiladas))):
                    try:
                        enlace = enlaces.nth(i)
                        href = enlace.get_attribute("href")
                        
                        if not href or "busqueda" in href:
                            continue
                        
                        if not href.startswith("http"):
                            href = f"https://www.bumeran.com.pe{href}"
                        
                        # ✅ CORRECCIÓN CLAVE: Extraer el título explícitamente del h2 o h3, no de la primera línea
                        try:
                            titulo_elem = enlace.locator("h2, h3").first
                            titulo = titulo_elem.inner_text().strip()
                        except Exception:
                            # Fallback: tomar la primera línea con más de 15 caracteres
                            texto_tarjeta = enlace.inner_text()
                            lineas = [l.strip() for l in texto_tarjeta.split('\n') if len(l.strip()) > 15]
                            titulo = lineas[0] if lineas else "Sin título"
                        
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        
                        # ✅ LOG DE DEPURACIÓN: Ver si el filtro lo está descartando
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            logger.debug(f"⏭️ Descartado por filtro: '{titulo}'")
                            continue
                        
                        # Abrir oferta
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                        self.page.wait_for_timeout(1000)
                        
                        self.page = self.page.context.pages[-1]
                        time.sleep(1.5)
                        self._destruir_modales()
                        
                        texto_crudo = self.obtener_texto_pagina()
                        if texto_crudo and len(texto_crudo) > 100:
                            ofertas_recopiladas.append({
                                "link_oferta": href,
                                "plataforma_origen": self.plataforma,
                                "texto_crudo": texto_crudo[:3000],
                                "titulo_puesto": titulo
                            })
                            # ✅ Cambiado a INFO para que lo veas en los logs
                            logger.info(f"✅ [{len(ofertas_recopiladas)}] Guardada: {titulo[:40]}...")
                        
                        self.page.close()
                        self.page = self.page.context.pages[0]
                        
                    except Exception as e:
                        logger.error(f"❌ Error procesando oferta {i}: {e}")
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                if count < 15:
                    logger.info("🏁 Página parcial detectada (< 15 ofertas), asumiendo última página real.")
                    break
                    
                pagina_actual += 1
                
            except Exception as e:
                logger.error(f"❌ Error crítico en página {pagina_actual}: {e}")
                self.debug_snapshot(f"bumeran_error_p{pagina_actual}")
                break
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas y listas para retornar")
        return ofertas_recopiladas
