# ============================================================================
# Módulo: scrapers/base_scraper.py
# ============================================================================

import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from loguru import logger

# Importar configuraciones
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import HEADLESS_MODE, TIMEOUT_SECONDS


class BaseScraper:
    """
    Clase base para todos los scrapers.
    Proporciona funcionalidades comunes: navegador, esperas, extracción de texto.
    """
    
    def __init__(self):
        self.driver = None
        self.wait = None
        self.logger = logger
        self.logger.info("✅ BaseScraper inicializado")
    
    def iniciar_navegador(self):
        """Inicializa el navegador Chrome con configuraciones estables."""
        self.logger.info("🌐 Configurando navegador Chrome...")
        chrome_options = Options()
        
        # Configuración ANTI-BLOQUEO y ESTABLE
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--ignore-certificate-errors")
        
        # Headless mode
        if HEADLESS_MODE:
            chrome_options.add_argument("--headless=new")
        
        try:
            # Usar webdriver-manager con configuración específica
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Configurar timeouts MÁS CORTOS para evitar session timeout
            self.driver.set_page_load_timeout(30)  # Reducido de 15 a 30
            self.driver.set_script_timeout(30)
            self.driver.implicitly_wait(10)  # Reducido de 15 a 10
            
            self.driver.maximize_window()
            self.wait = WebDriverWait(self.driver, 15, poll_frequency=0.5)
            
            self.logger.info("✅ Navegador iniciado con éxito")
            return self.driver
            
        except Exception as e:
            self.logger.error(f"❌ Error iniciando navegador: {e}")
            raise
    
    def obtener_texto_pagina(self, url: str) -> str:
        """Navega a una URL y extrae todo el texto visible de la página."""
        if not self.driver:
            self.iniciar_navegador()
        
        try:
            self.logger.info(f"🕵️ Extrayendo información de: {url[:80]}...")
            self.driver.get(url)
            time.sleep(2)  # Esperar carga inicial
            
            # Extraer todo el texto del body
            texto_crudo = self.driver.find_element("tag name", "body").text
            self.logger.debug(f"✅ Extraídos {len(texto_crudo)} caracteres")
            return texto_crudo
            
        except TimeoutException:
            self.logger.error(f"❌ Timeout al cargar {url}")
            return None
        except Exception as e:
            self.logger.error(f"❌ Error al extraer de {url}: {e}")
            return None
    
    def esperar_elemento(self, by, selector, timeout: int = None):
        """Espera a que un elemento esté presente en la página"""
        try:
            wait_time = timeout or TIMEOUT_SECONDS
            wait = WebDriverWait(self.driver, wait_time)
            return wait.until(EC.presence_of_element_located((by, selector)))
        except TimeoutException:
            self.logger.warning(f"⚠️ Elemento no encontrado: {selector}")
            return None
    
    def cerrar_navegador(self):
        """Cierra la sesión del navegador de forma segura."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None
            self.logger.info("🔒 Navegador cerrado de forma segura")


# ============================================================================
# TEST RÁPIDO
# ============================================================================

if __name__ == "__main__":
    print("="*50)
    print("PRUEBA DE BASE_SCRAPER")
    print("="*50)
    
    scraper = BaseScraper()
    scraper.iniciar_navegador()
    
    # Probar con una URL simple
    texto = scraper.obtener_texto_pagina("https://www.google.com")
    if texto:
        print(f"\n✅ Texto obtenido: {texto[:200]}...")
    else:
        print("\n❌ No se obtuvo texto")
    
    scraper.cerrar_navegador()