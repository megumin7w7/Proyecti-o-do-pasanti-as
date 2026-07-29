"""
Módulo: scrapers/bumeran_scraper.py (Control de flujo robusto)
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
        
        # 1. ✅ EL ACUMULADOR VIVE FUERA DE CUALQUIER TRY/EXCEPT PARA SOBREVIVIR A CUALQUIER FALLO
        ofertas_recopiladas = []
        
        if not self.page:
            self.iniciar_navegador(headless=True)
            
        puesto_slug = puesto.lower().replace(" ", "-")
        pagina_actual = 1
        
        # 2. ✅ EL LOOP PRINCIPAL MANEJA SUS PROPIOS ERRORES SIN BORRAR EL ACUMULADOR
        while len(ofertas_recopiladas) < limite_ofertas:
            try:
                if pagina_actual == 1:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html"
                else:
                    url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html?page={pagina_actual}"
                    
                logger.info(f"🔍 Bumeran (Pág {pagina_actual}): {url_busqueda}")
                
                # Navegar y esperar carga básica
                self.page.goto(url_busqueda, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                self._destruir_modales()
                
                # Aplicar filtro de ubicación si existe (solo en página 1)
                if lugar and pagina_actual == 1:
                    try:
                        input_lugar = self.page.locator("input[aria-label='Lugar de trabajo']").first
                        input_lugar.fill(lugar.capitalize())
                        self.page.keyboard.press("Enter")
                        # Esperar a que la red se calme o aparezcan resultados
                        self.page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info(f"📍 Filtro de ubicación aplicado: {lugar}")
                    except Exception as e:
                        logger.warning(f"⚠️ No se pudo aplicar filtro de ubicación: {e}")
                
                self.scroll_al_final()
                time.sleep(1.5)
                
                # 3. ✅ ESPERAR EXPLÍCITAMENTE. SI FALLA, ES EL FIN DE LA PAGINACIÓN, NO UN ERROR FATAL
                selector_ofertas = "a[href*='-aviso-'], a[href*='/empleos/']"
                try:
                    self.page.wait_for_selector(selector_ofertas, timeout=8000)
                except Exception:
                    logger.info(f"🏁 Bumeran: Fin de paginación en página {pagina_actual} (no se encontraron más enlaces)")
                    break  # 👈 CORRECTO: Rompe el loop, NO retorna vacío
                
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
                        texto_tarjeta = enlace.inner_text()
                        
                        if not href or "busqueda" in href:
                            continue
                        
                        # Completar URL
                        if not href.startswith("http"):
                            href = f"https://www.bumeran.com.pe{href}"
                        
                        lineas = [l.strip() for l in texto_tarjeta.split('\n') if l.strip()]
                        if not lineas:
                            continue
                        
                        titulo = lineas[0]
                        
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
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
                                "texto_crudo": texto_crudo[:3000], # ✅ Descripción completa
                                "titulo_puesto": titulo
                            })
                            logger.debug(f"✅ [{len(ofertas_recopiladas)}] {titulo[:35]}...")
                        
                        self.page.close()
                        self.page = self.page.context.pages[0]
                        
                    except Exception as e:
                        logger.error(f"❌ Error procesando oferta {i}: {e}")
                        # Asegurar retorno a la página principal
                        if len(self.page.context.pages) > 1:
                            self.page.close()
                            self.page = self.page.context.pages[0]
                
                # 4. ✅ HEURÍSTICA DE FIN DE PAGINACIÓN: Si la página tenía menos de 15 ofertas, no pedir la siguiente
                if count < 15:
                    logger.info("🏁 Página parcial detectada (< 15 ofertas), asumiendo última página real.")
                    break
                    
                pagina_actual += 1
                
            except Exception as e:
                # 5. ✅ SI ALGO FALLA CATASTRÓFICAMENTE, REGISTRAMOS EL ERROR PERO DEVOLVEMOS LO ACUMULADO
                logger.error(f"❌ Error crítico en página {pagina_actual}: {e}")
                self.debug_snapshot(f"bumeran_error_p{pagina_actual}")
                break # Rompe el loop, pero el código continúa hasta el return final
        
        # 6. ✅ SIEMPRE RETORNA EL ACUMULADOR, INCLUSO SI HUBO UN BREAK O UNA EXCEPCIÓN
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas y listas para retornar")
        return ofertas_recopiladas
