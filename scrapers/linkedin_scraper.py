# ============================================================================
# Módulo: scrapers/linkedin_scraper.py
# ============================================================================

import time
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from scrapers.base_scraper import BaseScraper
from loguru import logger

class LinkedInScraper(BaseScraper):
    """Scraper específico para LinkedIn usando URLs paginadas y expansión de texto"""
    
    def __init__(self):
        super().__init__()
        self.plataforma = "LinkedIn"
        logger.info("✅ LinkedInScraper inicializado")

    def _destruir_modales(self):
        """Usa JavaScript para eliminar cualquier cuadro de login que bloquee la pantalla"""
        try:
            self.driver.execute_script("""
                document.querySelectorAll('[role="dialog"], .modal, .contextual-sign-in-modal').forEach(e => e.remove());
                document.body.style.overflow = 'auto';
            """)
            logger.debug("🧹 Modales de login destruidos por JS.")
        except Exception:
            pass

    def recolectar_ofertas(self, url_semilla: str, limite_ofertas: int = 20, puesto: str = "practicante", lugar: str = "peru", filtro_relevancia_cb=None) -> list:
        if not self.driver:
            self.iniciar_navegador()

        ofertas_recopiladas = []
        
        # Validar que no lleguen vacíos
        puesto_seguro = puesto if puesto else "practicante"
        lugar_seguro = lugar if lugar else "peru"
        
        puesto_url = urllib.parse.quote(puesto_seguro)
        lugar_url = urllib.parse.quote(lugar_seguro)
        
        offset = 0 
        paginas_revisadas = 0
        max_paginas = 2 # Límite para pruebas rápidas
        
        while len(ofertas_recopiladas) < limite_ofertas and paginas_revisadas < max_paginas:
            url_busqueda = f"https://www.linkedin.com/jobs/search/?keywords={puesto_url}&location={lugar_url}&start={offset}"
            
            logger.info(f"🚀 LinkedIn (Pág {paginas_revisadas + 1}): {url_busqueda}")
            self.driver.get(url_busqueda)
            time.sleep(3) 
            
            self._destruir_modales()
            
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Ampliamos los selectores para agarrar bien las tarjetas
            tarjetas = self.driver.find_elements(By.CSS_SELECTOR, "div.base-card, div.job-search-card, li.jobs-search-results__list-item, div.job-card-container")
            
            if not tarjetas:
                logger.warning("⚠️ No se encontraron tarjetas en esta página.")
                break
                
            for elem in tarjetas:
                if len(ofertas_recopiladas) >= limite_ofertas:
                    break
                    
                try:
                    try:
                        enlace_elem = elem.find_element(By.CSS_SELECTOR, "a.base-card__full-link, a.job-card-container__link, a.job-card-list__title, a")
                        href = enlace_elem.get_attribute("href")
                        titulo_lista = enlace_elem.text.strip()
                    except NoSuchElementException:
                        continue
                        
                    if not href or "job" not in href.lower():
                        continue
                        
                    if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                        continue
                        
                    if filtro_relevancia_cb and not filtro_relevancia_cb(titulo_lista, puesto_seguro):
                        continue
                        
                    logger.debug(f"📦 Abriendo vacante: {titulo_lista[:35]}...")
                    self.driver.execute_script(f"window.open('{href}', '_blank');")
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    time.sleep(3)
                    
                    self._destruir_modales()
                    
                    # =========================================================
                    # ⚡ EL BLOQUE MÁGICO: CLIC EN "VER MÁS" Y EXTRACCIÓN COMPLETA
                    # =========================================================
                    try:
                        # 1. Intentar hacer clic en el botón "Ver más"
                        try:
                            btn_ver_mas = self.driver.find_element(By.CSS_SELECTOR, "button.show-more-less-html__button, button.jobs-description__footer-button")
                            self.driver.execute_script("arguments[0].click();", btn_ver_mas)
                            time.sleep(1.5) # Espera a que el texto baje
                        except NoSuchElementException:
                            pass # Si no hay botón, continuamos normal
                            
                        # 2. Capturar TODO EL CONTENEDOR CENTRAL (Encabezado con Empresa + Descripción)
                        # Usamos 'main' o 'section.core-rail' para agarrar la oferta entera sin el menú superior
                        cuerpo = self.driver.find_element(By.CSS_SELECTOR, "main, section.core-rail")
                        texto_crudo = cuerpo.text
                        
                    except NoSuchElementException:
                        logger.debug("⚠️ No se encontró 'main', usando respaldo (body)...")
                        try:
                            cuerpo = self.driver.find_element(By.TAG_NAME, "body")
                            texto_crudo = cuerpo.text
                        except:
                            texto_crudo = ""
                    # =========================================================
                    
                    if texto_crudo and len(texto_crudo) > 100:
                        ofertas_recopiladas.append({
                            "link_oferta": href,
                            "plataforma_origen": self.plataforma,
                            "texto_crudo": texto_crudo,
                            "titulo_puesto": titulo_lista
                        })
                        
                except Exception as e:
                    pass
                finally:
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                        self.driver.switch_to.window(self.driver.window_handles[0])
            
            offset += 25
            paginas_revisadas += 1
            
        return ofertas_recopiladas