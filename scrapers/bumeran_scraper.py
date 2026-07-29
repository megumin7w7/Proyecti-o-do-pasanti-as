"""
Módulo: scrapers/bumeran_scraper.py (Extracción rápida sin abrir ofertas)
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
                # URL correcta
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
                
                # ⚡ ESTRATEGIA RÁPIDA: Buscar tarjetas de ofertas completas
                # Usamos selectores que capturen los artículos completos
                selectores_tarjetas = [
                    "article",  # Bumeran usa <article> para cada oferta
                    ".offer-card",
                    "[class*='job-card']",
                    "div[data-qa='offer']"
                ]
                
                tarjetas = None
                for selector in selectores_tarjetas:
                    try:
                        tarjetas = self.obtener_elementos(selector)
                        if tarjetas.count() > 0:
                            logger.info(f"✅ Selector '{selector}' encontró {tarjetas.count()} tarjetas")
                            break
                    except:
                        continue
                
                if not tarjetas or tarjetas.count() == 0:
                    logger.warning(f"⚠️ No se encontraron tarjetas en página {pagina_actual}")
                    break
                
                # Procesar CADA tarjeta extrayendo TODO sin abrir
                for i in range(min(tarjetas.count(), limite_ofertas - len(ofertas_recopiladas))):
                    try:
                        tarjeta = tarjetas.nth(i)
                        
                        # 1. Extraer enlace
                        try:
                            enlace_elem = tarjeta.locator("a[href*='/empleos/']").first
                            href = enlace_elem.get_attribute("href")
                            if not href:
                                continue
                            if not href.startswith("http"):
                                href = f"https://www.bumeran.com.pe{href}"
                        except:
                            continue
                        
                        # 2. Extraer título (h2 o h3)
                        try:
                            titulo_elem = tarjeta.locator("h2, h3, .sc-VigVT").first
                            titulo = titulo_elem.inner_text().strip()
                        except:
                            titulo = ""
                        
                        # 3. Extraer empresa
                        try:
                            empresa_elem = tarjeta.locator(".sc-VigVT, h3").nth(1)
                            empresa = empresa_elem.inner_text().strip()
                        except:
                            empresa = ""
                        
                        # 4. Extraer descripción completa (está en el HTML que me mostraste)
                        try:
                            desc_elem = tarjeta.locator("p.sc-VigVT, [class*='description']")
                            descripcion = ""
                            for j in range(desc_elem.count()):
                                texto = desc_elem.nth(j).inner_text()
                                if len(texto) > 50:  # Tomar el párrafo más largo
                                    descripcion = texto
                                    break
                        except:
                            descripcion = ""
                        
                        # 5. Construir texto crudo completo
                        texto_crudo = f"{titulo}\n{empresa}\n{descripcion}"
                        
                        if len(texto_crudo) < 100:
                            logger.debug(f"⏭️ Descartada (texto corto): {titulo[:30]}")
                            continue
                        
                        # Verificar duplicados y filtro
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo, puesto):
                            continue
                        
                        # Guardar oferta SIN abrir
                        ofertas_recopiladas.append({
                            "link_oferta": href,
                            "plataforma_origen": self.plataforma,
                            "texto_crudo": texto_crudo[:2000],
                            "titulo_puesto": titulo
                        })
                        logger.info(f"✅ [{len(ofertas_recopiladas)}] {titulo[:40]}...")
                        
                    except Exception as e:
                        logger.debug(f"Error en tarjeta {i}: {e}")
                        continue
                
                logger.info(f"📦 Página {pagina_actual}: {len(ofertas_recopiladas)} ofertas acumuladas")
                pagina_actual += 1
                
                if pagina_actual > 5:
                    logger.info("🏁 Límite de 5 páginas alcanzado.")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Error crítico en Bumeran: {e}")
        
        logger.info(f"✅ Total Bumeran: {len(ofertas_recopiladas)} ofertas extraídas")
        return ofertas_recopiladas
