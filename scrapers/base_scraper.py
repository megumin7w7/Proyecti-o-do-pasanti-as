import time
import platform
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from loguru import logger
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import HEADLESS_MODE, TIMEOUT_SECONDS

class BaseScraper:
    """Clase base para todos los scrapers con configuraciones antibloqueo."""
    def __init__(self):
        self.driver = None
        self.wait = None
        self.logger = logger
        self.logger.info("✅ BaseScraper inicializado")

    def _encontrar_chromedriver(self):
        """Busca chromedriver en rutas comunes de Linux."""
        rutas_posibles = [
            '/usr/bin/chromedriver',
            '/usr/local/bin/chromedriver',
            '/snap/bin/chromedriver',
            '/usr/lib/chromium-browser/chromedriver',
            '/usr/lib/chromium/chromedriver'
        ]
        
        for ruta in rutas_posibles:
            if os.path.exists(ruta):
                self.logger.info(f"🔍 Chromedriver encontrado en: {ruta}")
                return ruta
        
        # Si no lo encuentra, usar webdriver-manager
        self.logger.info("️ Chromedriver no encontrado en rutas del sistema, usando webdriver-manager")
        return ChromeDriverManager().install()

    def iniciar_navegador(self):
        """Inicializa el navegador Chrome con configuraciones antibloqueo."""
        self.logger.info("🌐 Configurando navegador Chrome...")
        chrome_options = Options()
        
        # 1. Configuraciones Anti-Detección y Estabilidad
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 2. 🚨 FIX CRÍTICO PARA RENDER (LINUX)
        if platform.system() == "Linux":
            chrome_options.binary_location = '/usr/bin/chromium'
            self.logger.info("🐧 Entorno Linux detectado: Usando /usr/bin/chromium")
            
            # Buscar chromedriver automáticamente
            driver_path = self._encontrar_chromedriver()
            service = Service(driver_path)
        else:
            # Windows / Mac local
            service = Service(ChromeDriverManager().install())
            
        # 3. Modo headless (sin interfaz gráfica)
        if HEADLESS_MODE:
            chrome_options.add_argument("--headless=new")
            
        # 4. Inicializar driver
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 5. Configurar tiempos de espera
        self.driver.implicitly_wait(TIMEOUT_SECONDS)
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, TIMEOUT_SECONDS)
        
        self.logger.info("✅ Navegador iniciado con éxito")
        return self.driver

    def obtener_texto_pagina(self, url: str) -> str:
        if not self.driver:
            self.iniciar_navegador()
        try:
            self.logger.info(f"🕵️ Extrayendo información de: {url[:80]}...")
            self.driver.get(url)
            time.sleep(2)
            texto_crudo = self.driver.find_element("tag name", "body").text
            self.logger.debug(f"✅ Extraídos {len(texto_crudo)} caracteres")
            return texto_crudo
        except TimeoutException:
            self.logger.error(f"❌ Timeout al cargar {url}")
            return None
        except Exception as e:
            self.logger.error(f" Error al extraer de {url}: {e}")
            return None

    def esperar_elemento(self, by, selector, timeout: int = None):
        try:
            wait_time = timeout or TIMEOUT_SECONDS
            wait = WebDriverWait(self.driver, wait_time)
            return wait.until(EC.presence_of_element_located((by, selector)))
        except TimeoutException:
            self.logger.warning(f"⚠️ Elemento no encontrado: {selector}")
            return None

    def cerrar_navegador(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None
            self.logger.info(" Navegador cerrado de forma segura")
