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
        url_busqueda = f"https://pe.linkedin.com/jobs/search?keywords={q_puesto}&location={q_lugar}&f_TPR=r2592000"
        
        self.logger.info(f"🚀 LinkedIn -> Navegando a: {url_busqueda}")
        
        if not self.navegar_a(url_busqueda, wait_until="domcontentloaded"):
            return ofertas
        
        # LinkedIn deslogueado usa "infinite scroll". Hacemos un poco de scroll.
        for _ in range(3):
            self.scroll_al_final()
            self.page.wait_for_timeout(1000)
            
        # ====================================================================
        # 1. FASE DE RECOLECCIÓN (Solo copiamos los links, sin abrir nada)
        # ====================================================================
        tarjetas = self.page.locator("a.base-card__full-link, a.job-search-card__title").all()
        enlaces_pendientes = []
        
        for tarjeta in tarjetas:
            if len(enlaces_pendientes) >= limite_ofertas: 
                break
                
            try:
                href = tarjeta.get_attribute("href")
                titulo = tarjeta.inner_text().strip()
                
                if not href: 
                    continue
                    
                href = href.split('?')[0] # Limpiamos basura de tracking en la URL
                
                # Evitamos duplicados antes de navegar
                if not any(e["link"] == href for e in enlaces_pendientes):
                    enlaces_pendientes.append({"link": href, "titulo": titulo})
                    
            except Exception as e:
                self.logger.debug(f"Error leyendo tarjeta básica: {e}")

        self.logger.info(f"🔗 Se encontraron {len(enlaces_pendientes)} enlaces válidos. Iniciando extracción...")

        # ====================================================================
        # 2. FASE DE EXTRACCIÓN (Visitamos cada link en la MISMA pestaña)
        # ====================================================================
        for item in enlaces_pendientes:
            href = item["link"]
            titulo = item["titulo"]
            
            try:
                # Usamos goto en la pestaña principal, máximo 10 segundos
                self.page.goto(href, wait_until="domcontentloaded", timeout=10000)
                
                # Cerramos modales molestos de "Inicia sesión"
                try:
                    self.page.evaluate("document.querySelectorAll('button.modal__dismiss, button.sign-in-modal__dismiss').forEach(b => b.click())")
                except: 
                    pass
                
                # Extraemos el texto
                try:
                    desc_locator = self.page.locator("div.show-more-less-html__markup, div.description__text").first
                    texto_crudo = desc_locator.inner_text(timeout=3000)[:3000]
                except:
                    # Fallback si no encuentra el contenedor específico
                    texto_crudo = self.page.inner_text("body", timeout=3000)[:3000]
                    
                if texto_crudo and len(texto_crudo) > 50:
                    ofertas.append({
                        "link_oferta": href, 
                        "plataforma_origen": self.plataforma,
                        "texto_crudo": texto_crudo, 
                        "titulo_puesto": titulo
                    })
                    self.logger.info(f"📦 Extrayendo: {titulo[:40]}")
                    
            except Exception as e:
                self.logger.debug(f"Saltando oferta de LinkedIn por demora (Timeout): {e}")
                
        return ofertas
