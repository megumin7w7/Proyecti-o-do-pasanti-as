# ============================================================================
# Módulo: scrapers/bumeran_scraper.py
# ============================================================================

import sys
import os
import time
import urllib.parse

# Agrega la carpeta "Proyectiño do pasantiñas" a las rutas que lee Python
raiz_proyecto = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if raiz_proyecto not in sys.path:
    sys.path.insert(0, raiz_proyecto)

from scrapers.base_scraper import BaseScraper
from loguru import logger
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class BumeranScraper(BaseScraper):
    """Scraper específico para Bumeran integrado con la arquitectura BaseScraper"""
    
    def __init__(self):
        super().__init__()
        self.plataforma = "Bumeran"
        logger.info("✅ BumeranScraper inicializado")

    def _destruir_modales(self):
        """Usa JavaScript para eliminar pop-ups de cookies o banners publicitarios"""
        try:
            self.driver.execute_script("""
                document.querySelectorAll('[class*="banner"], [id*="cookie"], [class*="modal"]').forEach(e => e.remove());
                document.body.style.overflow = 'auto';
            """)
            logger.debug("🧹 Modales molestos eliminados por JS.")
        except Exception:
            pass

    def recolectar_ofertas(self, url_semilla: str, limite_ofertas: int = 20, puesto: str = "analista de datos", lugar: str = "lima", filtro_relevancia_cb=None) -> list:
        if not self.driver:
            self.iniciar_navegador()

        ofertas_recopiladas = []
        puesto_slug = puesto.lower().replace(" ", "-") if puesto else "empleos"
        pagina_actual = 1
        
        # 🔄 Bucle Dinámico: Avanza infinitamente hasta llenar el límite o agotar las páginas
        while len(ofertas_recopiladas) < limite_ofertas:
            
            if pagina_actual == 1:
                url_busqueda = f"https://www.bumeran.com.pe/empleos-busqueda-{puesto_slug}.html"
                logger.info(f"🚀 Navegando en Bumeran (Pág {pagina_actual}): {url_busqueda}")
                self.driver.get(url_busqueda)
                time.sleep(4)  
                
                self._destruir_modales()
                
                # 🎯 AQUÍ VA EL CÓDIGO CORREGIDO PARA EL MENÚ DE REACT
                # 🎯 AQUÍ VA EL NUEVO CÓDIGO PARA EL FILTRO DE UBICACIÓN
                if lugar:
                    try:
                        lugar_formateado = lugar.capitalize()
                        logger.info(f"📍 Escribiendo '{lugar_formateado}' en el filtro de ubicación...")
                        
                        wait = WebDriverWait(self.driver, 10)
                        
                        # 1. Buscamos el input exacto usando el aria-label (que es estático y seguro)
                        xpath_input = "//input[@aria-label='Lugar de trabajo']"
                        
                        # Usamos presence_of_element en lugar de clickable porque a veces el input está "escondido" bajo el div
                        input_lugar = wait.until(EC.presence_of_element_located((By.XPATH, xpath_input)))
                        
                        # 2. Hacemos scroll hacia la caja por si está fuera de pantalla
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", input_lugar)
                        time.sleep(0.5)
                        
                        # 3. Forzamos el clic para activar el cursor
                        self.driver.execute_script("arguments[0].click();", input_lugar)
                        time.sleep(0.5)
                        
                        # 4. Escribimos la ciudad y simulamos presionar la tecla "ENTER"
                        input_lugar.send_keys(lugar_formateado)
                        time.sleep(1)  # Pausa crítica para que React dibuje las opciones desplegables
                        input_lugar.send_keys(Keys.RETURN)
                        
                        logger.info("⏳ Esperando que Bumeran actualice los resultados de ubicación...")
                        time.sleep(5) 
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Fallo al interactuar con el filtro de ubicación: {e}")
            else:
                try:
                    logger.info(f"➡️ Pasando a la página {pagina_actual} mediante URL...")
                    url_actual = self.driver.current_url
                    
                    import re
                    # Si la URL ya tiene un parámetro de página, lo actualizamos
                    if "page=" in url_actual:
                        nueva_url = re.sub(r'([?&])page=\d+', rf'\g<1>page={pagina_actual}', url_actual)
                    else:
                        # Si no lo tiene, se lo agregamos (usando ? o & según corresponda)
                        conector = "&" if "?" in url_actual else "?"
                        nueva_url = f"{url_actual}{conector}page={pagina_actual}"
                        
                    self.driver.get(nueva_url)
                    time.sleep(4)  # Damos tiempo a que cargue la nueva página
                    self._destruir_modales()
                except Exception as e:
                    logger.error(f"🏁 Error al intentar cambiar de página por URL: {e}")
                    break
            
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            enlaces_potenciales = self.driver.find_elements(By.TAG_NAME, "a")
            enlaces_ofertas = []
            
            # Filtro para limpiar basura y fechas de publicación
            etiquetas_basura = ["Nuevo", "Destacado", "Urgente", "Sponsor", "Súper postulación"]
            
            for elem in enlaces_potenciales:
                try:
                    href = elem.get_attribute("href")
                    if href and ("-aviso-" in href or "/empleos/" in href) and "busqueda" not in href:
                        
                        texto_tarjeta = elem.text
                        if lugar and lugar.lower() not in texto_tarjeta.lower():
                            continue
                        
                        textos_crudos = texto_tarjeta.split('\n')
                        textos_limpios = []
                        
                        for t in textos_crudos:
                            texto_linea = t.strip()
                            if not texto_linea: continue
                            if texto_linea in etiquetas_basura: continue
                            if "Publicado" in texto_linea: continue
                            textos_limpios.append(texto_linea)
                        
                        if textos_limpios:
                            titulo_real = textos_limpios[0]
                            enlaces_ofertas.append((href, titulo_real))
                except:
                    continue
            
            if not enlaces_ofertas:
                logger.warning(f"⚠️ No se encontraron ofertas válidas para {lugar} en la página {pagina_actual}.")
                break
                
            logger.info(f"📄 Se detectaron {len(enlaces_ofertas)} enlaces correctos. Iniciando extracción...")
            
            for href, titulo_lista in enlaces_ofertas:
                if len(ofertas_recopiladas) >= limite_ofertas:
                    break
                    
                if any(o['link_oferta'] == href for o in ofertas_recopiladas):
                    continue
                    
                if filtro_relevancia_cb and titulo_lista and not filtro_relevancia_cb(titulo_lista, puesto):
                    continue
                    
                try:
                    logger.debug(f"📦 Abriendo vacante: {titulo_lista[:30]}...")
                    self.driver.execute_script(f"window.open('{href}', '_blank');")
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    
                    time.sleep(2.5) 
                    self._destruir_modales()
                    
                    texto_crudo = self.driver.find_element(By.TAG_NAME, "body").text
                    
                    if texto_crudo and len(texto_crudo) > 100:
                        ofertas_recopiladas.append({
                            "link_oferta": href,
                            "plataforma_origen": self.plataforma,
                            "texto_crudo": texto_crudo,
                            "titulo_puesto": titulo_lista 
                        })
                        
                except Exception as e:
                    logger.error(f"❌ Error al procesar oferta individual: {e}")
                finally:
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                        self.driver.switch_to.window(self.driver.window_handles[0])
            
            pagina_actual += 1
            
        return ofertas_recopiladas

# ============================================================================
# EJECUCIÓN DIRECTA PARA PRUEBA
# ============================================================================

if __name__ == "__main__":
    logger.remove()
    logger.add(lambda msg: print(msg, end=""))
    
    print("\n" + "="*50)
    print("PRUEBA DE BUMERAN SCRAPER (CON BASE_SCRAPER)")
    print("="*50 + "\n")
    
    scraper = BumeranScraper()
    
    resultados = scraper.recolectar_ofertas(
        url_semilla="", 
        limite_ofertas=50,
        puesto="analista de datos",
        lugar="Lima"
    )
    
    if resultados:
        print(f"\n✅ Se extrajeron {len(resultados)} ofertas totales:")
        for i, oferta in enumerate(resultados, 1):
            print(f"\n📌 Oferta [{i}]:")
            print(f"   Título: {oferta.get('titulo_puesto', 'N/A')}")
            print(f"   Link: {oferta.get('link_oferta', 'N/A')}")
            print(f"   Fragmento texto: {oferta.get('texto_crudo', 'N/A')[:100]}...")
    else:
        print("\n⚠️ No se extrajo ninguna oferta")
    
    scraper.cerrar_navegador()