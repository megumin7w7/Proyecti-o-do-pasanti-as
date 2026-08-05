# ============================================================================
# Módulo: bot_test_formulario.py (Versión 2.0 - Dropdowns Personalizados y Navegación)
# ============================================================================

import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def interactuar_dropdown_react(driver, wait, label_id_o_texto, valor_buscar):
    """
    Simula clics reales para abrir los dropdowns personalizados de React
    y seleccionar la opción correcta por su texto visible.
    """
    try:
        # 1. Intentamos buscar el botón del dropdown usando su texto o etiquetas cercanas
        xpath_dropdown = f"//button[contains(., '{label_id_o_texto}') or contains(@id, '{label_id_o_texto}')]"
        dropdown_btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_dropdown)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_btn)
        time.sleep(0.2)
        dropdown_btn.click()
        time.sleep(0.4) # Esperamos a que se despliegue la lista flotante
        
        # 2. Hacemos clic en la opción que coincida exactamente con nuestro valor de interés
        xpath_opcion = f"//div[@role='option' or @role='menuitem' or contains(@class, 'option')][normalize-space()='{valor_buscar}'] | //span[normalize-space()='{valor_buscar}']"
        opcion_seleccionar = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_opcion)))
        opcion_seleccionar.click()
        time.sleep(0.3)
        print(f"   ✅ Dropdown exitoso: [{label_id_o_texto}] -> '{valor_buscar}'")
    except Exception as e:
        print(f"   ⚠️ No se pudo interactuar de forma nativa con el dropdown [{label_id_o_texto}]: {e}")

def probar_llenado_en_produccion():
    
    
    vacante_prueba = {
        "titulo_puesto": "Practicante de Contabilidad",
        "empresa": "CARTAVIO RUM COMPANY S.A.C.",
        "plataforma_origen": "Bumeran",
        "modalidad": "Híbrido",
        "nivel": "Práctica",
        "horario": "Tiempo Completo",
        "departamento": "Lima",
        "area_categoria": "Contabilidad",
        "link_oferta": "https://www.bumeran.com.pe/empleos/practicante-de-contabilidad-cartavio-rum-con",
        "descripcion_breve": "Somos CartavioRumCo!!! Empresa con más de 96 años dedicados a la fabricación y comercialización de bebidas alcohólicas...",
        "beneficios": "• Seguro FOLA cubierto al 100%.\n• Póliza de seguro oncológico Oncoplus al 100%.",
        "requisitos": '[{"texto": "Estudiantes de últimos ciclos o egresados de la carrera de contabilidad.", "tipo": "Indispensable"}, {"texto": "Experiencia de 3 meses en posiciones afines al puesto.", "tipo": "Deseable"}]'
    }

    print("🚀 Iniciando navegador Chrome...")
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)
    driver = webdriver.Chrome(options=options)
    
    driver.get("https://gestion-comercial-eight.vercel.app/login")
    driver.maximize_window()
    wait = WebDriverWait(driver, 15)
    
    try:
        # 🔑 --- 1. PROCESO DE LOGIN ---
        print("🔐 Iniciando sesión en Laboral.AI...")
        email_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
        email_input.send_keys("test@laboral.ai")
        
        pass_input = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_input.send_keys("test1234")
        
        btn_login = driver.find_element(By.XPATH, "//button[contains(., 'Entrar al Dashboard')]")
        btn_login.click()
        
        # 🗺️ --- 2. NAVEGACIÓN COMPLEMENTARIA (OFERTAS LABORALES) ---
        print("📥 Buscando módulo 'Ofertas Laborales' en la barra lateral...")
        # Localizamos el botón del menú izquierdo usando el texto exacto de la captura
        menu_ofertas = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(., 'Ofertas Laborales')] | //a[contains(., 'Ofertas Laborales')]")))
        menu_ofertas.click()
        
        # 🎯 --- 3. APERTURA DEL FORMULARIO ---
        print("📥 Abriendo formulario de vacantes externas...")
        
        # Esperamos a que el botón esté presente en el HTML
        btn_nueva_oferta = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Nueva Oferta External') or contains(., 'Nueva Oferta Externa')]")))
        
        # 🌟 CLIC FORZADO POR JAVASCRIPT (Para esquivar cualquier overlay de carga)
        driver.execute_script("arguments[0].click();", btn_nueva_oferta)
        
        # Esperamos un momento a que el modal/formulario se despliegue en pantalla
        time.sleep(2.0)
        
        # ✍️ --- 4. LLENADO DE CAMPOS DE TEXTO DIRECTOS ---
        print("✍️ Llenando campos principales de la vacante...")
        
        titulo_field = wait.until(EC.presence_of_element_located((By.XPATH, "//label[contains(., 'Título del puesto')]/following-sibling::input | //input[contains(@placeholder, 'Analista de Datos')]")))
        titulo_field.send_keys(vacante_prueba["titulo_puesto"])
        
        empresa_field = driver.find_element(By.XPATH, "//label[contains(., 'Empresa')]/following-sibling::input | //input[contains(@placeholder, 'BBVA')]")
        empresa_field.send_keys(vacante_prueba["empresa"])
        
        link_field = driver.find_element(By.XPATH, "//input[@type='url' or contains(@placeholder, 'https://')]")
        link_field.send_keys(vacante_prueba["link_oferta"])
        
        # 🟢 --- 5. LLENADO DE DROPDOWNS CUSTOM CON CLICS ---
        print("🟢 Sincronizando selectores desplegables complejos...")
        
        interactuar_dropdown_react(driver, wait, "Seleccionar plataforma", vacante_prueba["plataforma_origen"])
        interactuar_dropdown_react(driver, wait, "Seleccionar modalidad", vacante_prueba["modalidad"])
        interactuar_dropdown_react(driver, wait, "Seleccionar nivel", vacante_prueba["nivel"])
        interactuar_dropdown_react(driver, wait, "Seleccionar horario", vacante_prueba["horario"])
        interactuar_dropdown_react(driver, wait, "Seleccionar departamento", vacante_prueba["departamento"])
        
        # ✍️ --- 6. COMPLETAR DESCRIPCIONES ---
        print("✍️ Completando descripciones...")
        
        area_field = driver.find_element(By.XPATH, "//label[contains(., 'Área')]/following-sibling::input | //input[contains(@placeholder, 'Marketing')]")
        area_field.send_keys(vacante_prueba["area_categoria"])
        
        desc_field = driver.find_element(By.XPATH, "//textarea[contains(@placeholder, 'Describe brevemente')]")
        desc_field.send_keys(vacante_prueba["descripcion_breve"])
        
        beneficios_field = driver.find_element(By.XPATH, "//textarea[contains(@placeholder, 'Seguro médico') or contains(., 'Beneficios')]")
        beneficios_field.send_keys(vacante_prueba["beneficios"])
        
        # 🛠️ --- 7. AGREGAR REQUISITOS DINÁMICOS (MÉTODO INTELIGENTE SIN ERRORES) ---
        print("🛠️ Insertando lista estructurada de Requisitos...")
        requisitos_lista = json.loads(vacante_prueba["requisitos"])
        
        for i, req in enumerate(requisitos_lista, 1):
            btn_agregar = driver.find_element(By.XPATH, "//button[contains(., 'Agregar requisito')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_agregar)
            time.sleep(0.2)
            driver.execute_script("arguments[0].click();", btn_agregar)
            time.sleep(0.6) # Esperamos el renderizado de la fila en React
            
            # 1. Escribir el texto en el último input
            inputs_req = driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'experiencia en Python')]")
            inputs_req[-1].send_keys(req["texto"])
            time.sleep(0.2)
            
            tipo_requisito = req["tipo"].strip().capitalize()
            
            # 2. Solo interactuamos con el selector si el tipo NO es el por defecto ("Indispensable")
            if tipo_requisito == "Deseable":
                print(f"   🔄 Cambiando prioridad del Requisito [{i}] a: 'Deseable'")
                
                # Localizamos el último botón del dropdown
                botones_tipo = driver.find_elements(By.XPATH, "//button[contains(., 'Indispensable') or contains(., 'Deseable')]")
                ultimo_boton_tipo = botones_tipo[-1]
                
                # Abrimos el desplegable con un clic forzado de JS (evita bloqueos de foco)
                driver.execute_script("arguments[0].click();", ultimo_boton_tipo)
                time.sleep(0.4)
                
                # Buscamos la opción "Deseable" en la lista flotante y le damos clic forzado
                xpath_deseable = "//div[@role='option' or @role='menuitem'][normalize-space()='Deseable'] | //span[normalize-space()='Deseable']"
                opcion_deseable = wait.until(EC.presence_of_element_located((By.XPATH, xpath_deseable)))
                driver.execute_script("arguments[0].click();", opcion_deseable)
                time.sleep(0.3)
            else:
                # Si es "Indispensable", lo dejamos tal cual porque React ya lo crea así por defecto
                print(f"   ✨ Requisito [{i}] se mantiene en 'Indispensable' (por defecto).")
            
            print(f"   ✅ Requisito [{i}] completado con éxito.")
        
    except Exception as e:
        print(f"❌ Error en el proceso de automatización: {e}")

if __name__ == "__main__":
    probar_llenado_en_produccion()