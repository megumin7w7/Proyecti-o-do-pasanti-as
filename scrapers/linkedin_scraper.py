"""
Módulo: scrapers/linkedin_scraper.py
"""
from urllib.parse import unquote
import re
from scrapers.base_scraper import BaseScraper
from utils.url_cleaner import normalizar_termino_busqueda

class LinkedInScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.plataforma = "LinkedIn"

    def recolectar_ofertas(self, limite_ofertas: int = 20, puesto: str = "", lugar: str = "", filtro_relevancia_cb=None, urls_existentes: set = None) -> list:
        if urls_existentes is None: urls_existentes = set()
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
                
                if not href: continue
                href = href.split('?')[0] # Limpiamos basura de tracking en la URL
                
                # === FILTRO DE MEMORIA COMPARTIDA ===
                if href in urls_existentes: continue
                
                if not any(e["link"] == href for e in enlaces_pendientes):
                    enlaces_pendientes.append({"link": href, "titulo": titulo})
                    urls_existentes.add(href) # Agregamos al Set global
                    
            except Exception as e:
                self.logger.debug(f"Error leyendo tarjeta básica: {e}")

        self.logger.info(f"🔗 Se encontraron {len(enlaces_pendientes)} enlaces válidos. Iniciando extracción...")
        # ====================================================================
        # 2. FASE DE EXTRACCIÓN (Visitamos cada link en la MISMA pestaña)
        # ====================================================================
        for item in enlaces_pendientes:
            
            if len(ofertas) >= limite_ofertas:
                self.logger.info(f"🎯 Límite de {limite_ofertas} ofertas alcanzado. Deteniendo extracción.")
                break
                
            href = item["link"]
            titulo = item["titulo"]
            
            try:
                # 🛠️ CORRECCIÓN 1: Volvemos a usar domcontentloaded para darle tiempo a LinkedIn
                self.navegar_a(href, wait_until="domcontentloaded", timeout=10000)
                
                # Intentamos cerrar el molesto banner de authwall si aparece
                try:
                    self.page.evaluate("""
                        document.querySelectorAll('button.modal__dismiss, button[aria-label="Dismiss"]').forEach(b => b.click());
                    """)
                except:
                    pass

                try:
                    # 🛠️ CORRECCIÓN 2: Selectores exactos y 5 segundos de espera
                    cuerpo = self.page.locator("div.show-more-less-html__markup, div.description__text, section.core-section-container").first
                    cuerpo.wait_for(state="visible", timeout=5000)
                    texto_crudo = cuerpo.inner_text()[:4000]
                except:
                    self.page.wait_for_timeout(2000)
                    texto_crudo = self.page.inner_text("body", timeout=2500)[:4000]
                
                # 🥷 TRUCO NINJA: Rescatar la empresa desde la URL
                empresa_ninja = ""
                match = re.search(r'-at-(.*?)-\d+$', href)
                if match:
                    # 1. Decodificamos caracteres extraños (ej. %C3%BA -> ú)
                    texto_url = unquote(match.group(1))
                    # 2. Quitamos guiones y capitalizamos
                    empresa_ninja = texto_url.replace('-', ' ').title()
                
                # Inyectamos el salvavidas al inicio del texto crudo
                if empresa_ninja:
                    texto_crudo = f"Somos {empresa_ninja}.\n\n" + (texto_crudo if texto_crudo else "")

                if texto_crudo and len(texto_crudo) > 50:
                    ofertas.append({
                        "link_oferta": href,
                        "plataforma_origen": self.plataforma,
                        "texto_crudo": texto_crudo,
                        "titulo_puesto": titulo
                    })
                    self.logger.debug(f"✅ Extrayendo: {titulo[:40]}...")
                    
            except Exception as e:
                self.logger.error(f"❌ Error extrayendo {titulo[:20]}: {e}")
                
        self.logger.info(f"✅ Total extraído LinkedIn: {len(ofertas)} ofertas")
        return ofertas
