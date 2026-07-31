"""
Módulo: scrapers/bumeran_scraper.py (Optimizado)
"""
from scrapers.base_scraper import BaseScraper
from utils.url_cleaner import normalizar_termino_busqueda

class BumeranScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.plataforma = "Bumeran"

    def _destruir_modales(self):
        """Elimina popups y banners que bloquean la navegación."""
        try:
            self.page.evaluate("""
                document.querySelectorAll('[class*="modal"], [class*="Popup"], button[class*="close"], div[id*="dfp"]').forEach(e => {
                    if (e.offsetParent !== null) e.click();
                });
            """)
        except:
            pass

    def recolectar_ofertas(self, limite_ofertas: int = 20, puesto: str = "", lugar: str = "", filtro_relevancia_cb=None) -> list:
        ofertas = []
        # Bumeran usa el formato de guiones (ej: analista-de-datos)
        slug_puesto = normalizar_termino_busqueda(puesto)["slug_guiones"]
        
        for pagina in range(1, 10):
            if len(ofertas) >= limite_ofertas: break
            
            url = f"https://www.bumeran.com.pe/empleos-busqueda-{slug_puesto}.html?page={pagina}" if pagina > 1 else f"https://www.bumeran.com.pe/empleos-busqueda-{slug_puesto}.html"
            
            self.logger.info(f"📄 Bumeran -> Página {pagina}: {url}")
            
            if not self.navegar_a(url, wait_until="commit"):
                break
                
            self._destruir_modales()
            
            # Selector genérico para tarjetas de empleo en Bumeran
            enlaces = self.page.locator("a[href*='/empleos/']").all()
            if not enlaces: 
                break
            
            for enlace in enlaces:
                if len(ofertas) >= limite_ofertas: break
                
                try:
                    href = enlace.get_attribute("href")
                    titulo = enlace.inner_text().strip() or puesto
                    
                    if not href: continue
                    if not href.startswith("http"): href = f"https://www.bumeran.com.pe{href}"
                    if any(o['link_oferta'] == href for o in ofertas): continue
                    
                    # Abrir la oferta en una pestaña optimizada
                    with self.context.expect_page() as nueva_pag_info:
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                    
                    nueva_pag = nueva_pag_info.value
                    nueva_pag.wait_for_load_state("commit")
                    
                    try:
                        # Extraer descripción específica de Bumeran
                        cuerpo = nueva_pag.locator("[id*='aviso-description'], [class*='aviso-description'], div[class*='Description']").first
                        texto_crudo = cuerpo.inner_text()[:3000]
                    except:
                        texto_crudo = nueva_pag.inner_text("body")[:3000]
                        
                    if texto_crudo and len(texto_crudo) > 50:
                        ofertas.append({
                            "link_oferta": href, 
                            "plataforma_origen": self.plataforma,
                            "texto_crudo": texto_crudo, 
                            # Tomar solo la primera línea si el título vino con texto extra
                            "titulo_puesto": titulo.split('\n')[0] 
                        })
                        self.logger.debug(f"✅ Extrayendo: {titulo[:40]}")
                        
                    nueva_pag.close()
                except Exception as e:
                    self.logger.debug(f"Error procesando oferta de Bumeran: {e}")
                    
        return ofertas
