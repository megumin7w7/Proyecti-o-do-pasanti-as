"""
Módulo: scrapers/linkedin_scraper.py (Optimizado)
"""
from scrapers.base_scraper import BaseScraper
from utils.url_cleaner import normalizar_termino_busqueda

class LinkedInScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.plataforma = "LinkedIn"

    def recolectar_ofertas(self, limite_ofertas: int = 20, puesto: str = "", lugar: str = "", filtro_relevancia_cb=None) -> list:
        ofertas = []
        
        # LinkedIn usa el formato de búsqueda con signos '+' (ej: analista+de+datos)
        q_puesto = normalizar_termino_busqueda(puesto)["slug_mas"]
        q_lugar = normalizar_termino_busqueda(lugar)["slug_mas"]
        
        # Parámetro f_TPR=r2592000 filtra por los últimos 30 días para evitar resultados viejos
        url = f"https://pe.linkedin.com/jobs/search?keywords={q_puesto}&location={q_lugar}&f_TPR=r2592000"
        
        self.logger.info(f"🚀 LinkedIn -> Navegando a: {url}")
        
        if not self.navegar_a(url, wait_until="domcontentloaded"):
            return ofertas
        
        # LinkedIn deslogueado usa "infinite scroll". Hacemos un poco de scroll.
        for _ in range(3):
            self.scroll_al_final()
            self.page.wait_for_timeout(1000)
            
        tarjetas = self.page.locator("a.base-card__full-link, a.job-search-card__title").all()
        
        for tarjeta in tarjetas:
            if len(ofertas) >= limite_ofertas: break
            
            try:
                href = tarjeta.get_attribute("href")
                titulo = tarjeta.inner_text().strip()
                
                if not href: continue
                
                # Limpiar los excesivos parámetros de rastreo que LinkedIn añade a las URLs
                href = href.split('?')[0]
                
                if any(o["link_oferta"] == href for o in ofertas): continue
                
                # Cargar la tarjeta en pestaña nueva
                with self.context.expect_page() as nueva_pag_info:
                    self.page.evaluate(f"window.open('{href}', '_blank')")
                
                nueva_pag = nueva_pag_info.value
                nueva_pag.wait_for_load_state("commit")
                
                # Cerrar modal persistente de "Inicia Sesión" si aparece
                try:
                    nueva_pag.evaluate("document.querySelectorAll('button.modal__dismiss, button.sign-in-modal__dismiss').forEach(b => b.click())")
                except: 
                    pass
                
                try:
                    # Div exacto donde LinkedIn coloca la descripción de la oferta
                    desc_locator = nueva_pag.locator("div.show-more-less-html__markup, div.description__text").first
                    texto_crudo = desc_locator.inner_text()[:3000]
                except:
                    texto_crudo = nueva_pag.inner_text("body")[:3000]
                    
                if texto_crudo and len(texto_crudo) > 50:
                    ofertas.append({
                        "link_oferta": href, 
                        "plataforma_origen": self.plataforma,
                        "texto_crudo": texto_crudo, 
                        "titulo_puesto": titulo
                    })
                    self.logger.info(f"📦 Extrayendo: {titulo[:40]}")
                    
                nueva_pag.close()
            except Exception as e:
                self.logger.debug(f"Error procesando tarjeta LinkedIn: {e}")
                
        return ofertas
