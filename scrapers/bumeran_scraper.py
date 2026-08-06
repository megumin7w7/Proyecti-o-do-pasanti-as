"""
Módulo: scrapers/bumeran_scraper.py (Corregido y Estable)
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

    def recolectar_ofertas(self, limite_ofertas: int = 20, puesto: str = "", lugar: str = "", filtro_relevancia_cb=None, urls_existentes: set = None) -> list:
        if urls_existentes is None: urls_existentes = set()
        ofertas = []
        slug_puesto = normalizar_termino_busqueda(puesto)["slug_guiones"]
        
        for pagina in range(1, 10):
            if len(ofertas) >= limite_ofertas: break
            
            url = f"https://www.bumeran.com.pe/empleos-busqueda-{slug_puesto}.html?page={pagina}" if pagina > 1 else f"https://www.bumeran.com.pe/empleos-busqueda-{slug_puesto}.html"
            
            self.logger.info(f"📄 Bumeran -> Página {pagina}: {url}")
            
            # 1. Esperamos a que el DOM cargue completo
            if not self.navegar_a(url, wait_until="domcontentloaded"):
                break
                
            self._destruir_modales()
            
            # 2. Obligamos a Playwright a esperar hasta que exista al menos una tarjeta
            try:
                self.page.wait_for_selector("a[href*='/empleos/']", timeout=3000)
            except:
                self.logger.warning(f"⚠️ No se encontraron ofertas a tiempo en Bumeran (Página {pagina})")
                break
            
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
                    
                    # === FILTRO DE MEMORIA COMPARTIDA ===
                    if href in urls_existentes: continue
                    if any(o['link_oferta'] == href for o in ofertas): continue
                    
                    # Inmediatamente lo guardamos para bloquearlo globalmente
                    urls_existentes.add(href) 
                    
                    with self.context.expect_page() as nueva_pag_info:
                        self.page.evaluate(f"window.open('{href}', '_blank')")
                    
                    nueva_pag = nueva_pag_info.value
                    
                    # 🛠️ CORRECCIÓN 1: Volvemos a 'domcontentloaded' para asegurar que la estructura esté lista
                    nueva_pag.wait_for_load_state("domcontentloaded", timeout=5000)
                    
                    try:
                        # 🛠️ CORRECCIÓN 2: Selector ampliado y espera de 5 segundos para que Bumeran inyecte el texto
                        cuerpo = nueva_pag.locator("[id*='aviso-description'], [class*='aviso-description'], div[class*='Description'], h2:has-text('Descripción') + div").first
                        cuerpo.wait_for(state="visible", timeout=5000)
                        texto_crudo = cuerpo.inner_text()[:4000]
                    except:
                        # Plan B: Si falla el selector, esperamos 2 segundos a la fuerza para que cargue lo que falta y leemos todo
                        nueva_pag.wait_for_timeout(2000)
                        texto_crudo = nueva_pag.inner_text("body", timeout=2000)[:4000]
                        
                    if texto_crudo and len(texto_crudo) > 50:
                        ofertas.append({
                            "link_oferta": href, 
                            "plataforma_origen": self.plataforma,
                            "texto_crudo": texto_crudo, 
                            "titulo_puesto": titulo.split('\n')[0] 
                        })
                        self.logger.debug(f"✅ Extrayendo: {titulo[:40]}")
                        
                except Exception as e:
                    self.logger.debug(f"Error procesando oferta de Bumeran: {e}")
                finally:
                    # Garantiza que la pestaña siempre se cierre, incluso si falla
                    if 'nueva_pag' in locals() and not nueva_pag.is_closed():
                        nueva_pag.close()
                    
        return ofertas
