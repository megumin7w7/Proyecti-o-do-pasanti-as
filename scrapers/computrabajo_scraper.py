# ============================================================================
# Módulo: scrapers/computrabajo_scraper.py
# ============================================================================

import sys
import os
import time

# Agregar raíz del proyecto al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from loguru import logger


class ComputrabajoScraper(BaseScraper):
    """Scraper específico para Computrabajo con soporte de paginación avanzada"""
    
    def __init__(self):
        super().__init__()
        self.plataforma = "Computrabajo"
        logger.info("✅ ComputrabajoScraper inicializado con Paginación Dinámica")

    def _eliminar_obstaculos(self):
        """Revisión ultrarrápida sin esperas de Selenium"""
        obstaculos = [
            "//button[contains(@class, 'modal-close')]", 
            "//div[contains(@id, 'cookie')]//button",
            "//button[contains(text(), 'Aceptar')]"
        ]
        # Cambiamos temporalmente a búsqueda inmediata para no perder tiempo
        self.driver.implicitly_wait(0)
        for xpath in obstaculos:
            try:
                # Si está lo clickea, si no, pasa en milisegundos sin esperar
                elemento = self.driver.find_element(By.XPATH, xpath)
                if elemento.is_displayed():
                    elemento.click()
                    logger.debug("🛡️ Banner removido al instante.")
            except:
                continue

    def recolectar_ofertas(self, url_semilla: str, limite_ofertas: int = 3, puesto: str = None, lugar: str = None, filtro_relevancia_cb=None) -> list:
        """
        Recolecta ofertas de forma exhaustiva analizando el 100% de las vacantes 
        en cada página (?p=X) sin saltarse elementos, usando paginación dinámica.
        """
        
        if not self.driver:
            self.iniciar_navegador()
            
        ofertas_recopiladas = []
        pagina_actual = 1
        
        # ⚡ CORTA-FUEGOS: Evita bucles infinitos si la web tiene errores. 
        # Revisará hasta 30 páginas, pero se detendrá antes si se acaban las ofertas.
        MAX_PAGINAS_SEGURIDAD = 30  
        
        # 1. Construcción limpia de la URL nativa
        puesto_query = puesto.lower().replace(" ", "-") if puesto else ""
        lugar_query = lugar.lower().replace(" ", "-") if lugar else ""
        
        if puesto_query and lugar_query:
            url_base_busqueda = f"https://pe.computrabajo.com/trabajo-de-{puesto_query}-en-{lugar_query}"
        elif puesto_query:
            url_base_busqueda = f"https://pe.computrabajo.com/trabajo-de-{puesto_query}"
        else:
            url_base_busqueda = url_semilla.rstrip('/')

        try:
            # ⚡ CONDICIÓN DOBLE: Seguir mientras no superemos las 30 páginas Y no hayamos alcanzado el límite.
            while pagina_actual <= MAX_PAGINAS_SEGURIDAD and len(ofertas_recopiladas) < limite_ofertas:
                url_con_pagina = f"{url_base_busqueda}?p={pagina_actual}"
                logger.info(f"🚀 Navegando a la Página {pagina_actual}: {url_con_pagina}")
                
                self.driver.get(url_con_pagina)
                
                # ⚡ TIEMPO DE ESPERA CALIBRADO: Asegura que el HTML y las ofertas carguen al 100%
                time.sleep(3.5)
                
                self._eliminar_obstaculos()
                
                # Capturar las ofertas de la página actual
                elementos_ofertas = self.driver.find_elements(By.CLASS_NAME, "js-o-link")
                
                # ⚡ EL FRENO DE VACÍO: Si no hay ofertas, la página está vacía. ¡Rompemos el ciclo!
                if not elementos_ofertas:
                    logger.warning(f"🏁 Se terminaron las páginas disponibles (Página {pagina_actual} vacía).")
                    break
                    
                logger.info(f"📄 Página {pagina_actual}: Analizando con calma las {len(elementos_ofertas)} ofertas del listado...")
                
                # ⚡ EXHAUSTIVO: Recorremos los elementos de la página actual
                for elem in elementos_ofertas:
                    
                    # ⚡ FRENO EXACTO: Si en medio de la página llegamos a la meta (ej. 50 ofertas), nos detenemos.
                    if len(ofertas_recopiladas) >= limite_ofertas:
                        break
                        
                    try:
                        href = elem.get_attribute("href")
                        titulo_lista = elem.text.strip()
                        
                        if not href or not titulo_lista:
                            continue
                            
                        # Evitar duplicados dentro de la misma sesión de raspado
                        if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                            continue
                        
                        # Aplicar tu filtro dinámico inteligente (Inmunidad a híbridos y discriminación de datos)
                        if filtro_relevancia_cb and not filtro_relevancia_cb(titulo_lista, puesto):
                            continue
                            
                        indice_actual = len(ofertas_recopiladas) + 1
                        logger.debug(f"📦 [{indice_actual}] Abriendo vacante válida: {titulo_lista[:35]}...")
                        
                        # Abrir la oferta para extraer el cuerpo de texto completo (NLP)
                        self.driver.execute_script(f"window.open('{href}', '_blank');")
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        
                        time.sleep(0.8)  # Pausa breve para garantizar que cargue el texto interno
                        texto_crudo = self.driver.find_element(By.TAG_NAME, "body").text
                        
                        if texto_crudo and len(texto_crudo) > 50:
                            ofertas_recopiladas.append({
                                "link_oferta": href,
                                "plataforma_origen": self.plataforma,
                                "texto_crudo": texto_crudo,
                                "titulo_puesto": titulo_lista
                            })
                            
                    except Exception as e:
                        logger.error(f"❌ Error en elemento individual: {e}")
                        
                    finally:
                        # Asegurar regresar siempre a la pestaña del listado principal
                        if len(self.driver.window_handles) > 1:
                            self.driver.close()
                            self.driver.switch_to.window(self.driver.window_handles[0])
                
                # Forzar el avance a la siguiente página en la URL
                pagina_actual += 1
                        
        except Exception as e:
            logger.error(f"❌ Error crítico en el proceso de recolección paginada: {e}")
        
        logger.info(f"📌 Total acumulado finalizado: {len(ofertas_recopiladas)} ofertas recopiladas para procesar.")
        return ofertas_recopiladas

# ============================================================================
# EJECUCIÓN DIRECTA PARA PRUEBA
# ============================================================================

if __name__ == "__main__":
    # Configurar logger simple para prueba
    logger.remove()
    logger.add(lambda msg: print(msg, end=""))
    
    print("\n" + "="*50)
    print("PRUEBA DE COMPUTRABAJO SCRAPER (CON PAGINACIÓN)")
    print("="*50 + "\n")
    
    scraper = ComputrabajoScraper()
    url_prueba = "https://pe.computrabajo.com/trabajo-de-programador-en-lima"
    
    # Prueba a pedirle 25 ofertas para ver cómo salta de la página 1 a la 2 automáticamente
    resultados = scraper.recolectar_ofertas(url_prueba, limite_ofertas=25)
    
    if resultados:
        print(f"\n✅ Se extrajeron {len(resultados)} ofertas totales:")
        for i, oferta in enumerate(resultados[-3:], 1): # Muestra un resumen de las últimas 3
            print(f"\n📌 Últimas Ofertas Extraídas [{i}]:")
            print(f"   Título: {oferta.get('titulo_puesto', 'N/A')}")
            print(f"   Link: {oferta.get('link_oferta', 'N/A')}")
    else:
        print("\n⚠️ No se extrajo ninguna oferta")
    
    scraper.cerrar_navegador()