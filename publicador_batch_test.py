# ============================================================================
# Módulo: publicador_batch_test.py (Versión Pro con Auto-Limpieza y Extractor de Empresa)
# ============================================================================

import json
import time
import sys
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Aseguramos importaciones locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from storage.sheets_handler import SheetsHandler

# ============================================================================
# 🧠 UTILIDADES DE LIMPIEZA SINTÁCTICA PARA TEXTOS DESORDENADOS
# ============================================================================

def normalizar_puntuacion_y_espacios(texto):
    """
    Arregla la puntuación rota típica de la minería de texto (ej: 'afines.Actitud' -> 'afines. Actitud')
    y limpia espacios duplicados o raros.
    """
    if not texto:
        return ""
    # Asegurar espacio después de puntos, comas o paréntesis si les sigue una mayúscula o número
    texto = re.sub(r'\.([A-ZÁÉÍÓÚ])', r'. \1', texto)
    texto = re.sub(r'\)([A-ZÁÉÍÓÚ])', r') \1', texto)
    texto = re.sub(r',([a-zA-ZÁÉÍÓÚáéíóú])', r', \1', texto)
    # Reemplazar múltiples espacios o tabulaciones por uno solo
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()


def segmentar_bloque_unido(texto_bloque):
    """
    Toma un bloque de texto que puede venir sin saltos de línea (ladrillo plano)
    y lo corta inteligentemente en una lista de requisitos o funciones individuales.
    """
    if not texto_bloque:
        return []
        
    texto_bloque = normalizar_puntuacion_y_espacios(texto_bloque)
    
    # Intentamos separar primero por saltos de línea reales si existen
    if "\n" in texto_bloque and len(texto_bloque.split("\n")) > 2:
        candidatos = [linea.strip() for linea in texto_bloque.split("\n") if len(linea.strip()) > 5]
    else:
        # Si es un bloque plano, dividimos usando patrones clave de inicio de viñeta o puntos seguidos con mayúscula
        patron_separador = r'(?=\b(?:Egresado|Experiencia|Conocimiento|Disponibilidad|Estudios|Manejo|Actitud|Capacidad|Orientación|Deseable|Indispensable)\b)|\.\s+(?=[A-ZÁÉÍÓÚ])|\)\s+(?=[A-ZÁÉÍÓÚ])'
        candidatos = [f.strip() for f in re.split(patron_separador, texto_bloque) if len(f.strip()) > 5]
        
    resultado = []
    for item in candidatos:
        # Limpieza de basura inicial de la viñeta (guiones, asteriscos, números)
        item_limpio = re.sub(r"^[•\-\*\s\d\.\)\-\s]+", "", item).strip()
        # Evitar colar sub-encabezados dentro de la lista de viñetas
        if item_limpio and not any(palabra in item_limpio.lower()[:20] for palabra in ["requisitos", "funciones", "ofrecemos", "horario", "perfil"]):
            resultado.append(item_limpio)
            
    return resultado

def extraer_nombre_empresa(titulo, descripcion_sucia_limpia):
    if not descripcion_sucia_limpia:
        return "Empresa Confidencial"
        
    # 1. Unificamos espacios y saltos de línea
    temp = re.sub(r'\s+', ' ', str(descripcion_sucia_limpia)).strip()

    # ============================================================================
    # 🧹 1. PURGA AGRESIVA DE MENÚS (Lista Negra General)
    # ============================================================================
    lista_negra_menus = [
        r"Buscar empleo por puesto(?: o palabra clave)?",
        r"Lugar de trabajo", r"Crear cuenta", r"Ingresar", r"Sitios de interés",
        r"Buscar empresas", r"Bolsa de empleo", r"Salarios", r"Blog",
        r"Login\s+Crear\s+CV\s+Volver\s+al\s+listado", r"Ofertas similares",
        r"Postularme", r"Postular", r"Seguir"
    ]
    for frase in lista_negra_menus:
        temp = re.sub(rf"\b{frase}\b", " ", temp, flags=re.IGNORECASE)
        
    # Limpieza extra: Borramos modalidades de trabajo si se pegaron al inicio
    temp = re.sub(r"\b(?:Presencial|Híbrido|Remoto|Tiempo completo|Medio tiempo)\b", " ", temp, flags=re.IGNORECASE)
    temp = re.sub(r'\s+', ' ', temp).strip() 

    # ============================================================================
    # 🔪 2. EL CUCHILLO UNIVERSAL (Corta por el Título)
    # ============================================================================
    palabras_titulo = re.findall(r'[a-zA-Z0-9ÁÉÍÓÚáéíóúñÑ]+', str(titulo))
    empresa_encontrada = None
    
    if palabras_titulo:
        # Busca el título en el texto bruto, sin importar la plataforma
        patron_titulo = r'[\s\W]*'.join(palabras_titulo)
        partes = re.split(patron_titulo, temp, flags=re.IGNORECASE)
        
        if len(partes) > 1:
            # Tomamos la última parte (todo lo que está a la derecha del último título detectado)
            resto = partes[-1].strip()
            # Limpiamos barras o guiones huérfanos que hayan quedado al cortar (Ej: " | MULTI BELAND")
            resto = re.sub(r"^[\s\|\-\/]+", "", resto).strip()
            
            # Extraemos las primeras palabras capitalizadas (la empresa)
            match_empresa = re.match(r"^((?:[A-ZÁÉÍÓÚ0-9][a-zA-ZÁÉÍÓÚa-záéíóú0-9ñÑ&\.\-]+\s*){1,4})", resto)
            if match_empresa:
                cand = match_empresa.group(1).strip()
                # Freno de emergencia por si agarró palabras de la descripción
                cand = re.split(r"(?:\b(?:Descripción|Requisitos|Funciones|Misión|El|La|En|Somos|Para|Acerca|Detalle)\b)", cand, flags=re.IGNORECASE)[0].strip()
                if len(cand) > 2:
                    empresa_encontrada = cand

    if empresa_encontrada:
        return empresa_encontrada

    # ============================================================================
    # 🛡️ 3. FALLBACK DE EMERGENCIA (Si el título no estaba en el texto)
    # ============================================================================
    # Aislamos el bloque superior antes de "Descripción" o "Oferta"
    match_bloque = re.search(r"^(.*?)(?=\s+(?:Oferta|Empresa|Salarios|Ofertas|O\b|Descripci))", temp, flags=re.IGNORECASE)
    bloque = match_bloque.group(1).strip() if match_bloque else temp
        
    bloque = re.sub(r"\s*-\s*[A-Za-zÁÉÍÓÚáéíóú\s]+(?:,\s*[A-Za-zÁÉÍÓÚáéíóú\s]+)?$", "", bloque).strip()
    distritos_ruido = r"^[-|/:\s\(\),]*(?:Lima|La Molina|Santiago de Surco|Surco|Surquillo|San Isidro|Miraflores|Arequipa|Callao|Trujillo|Chiclayo|Piura|Cusco)\b[\s\-|,]*"
    bloque = re.sub(distritos_ruido, "", bloque, flags=re.IGNORECASE).strip()
    
    empresa = re.sub(r"^[-|/:\s\(\),]+|[-|/:\s\(\),]+$", "", bloque).strip()
    
    if not empresa or len(empresa) < 3 or "importante empresa" in empresa.lower() or "confidencial" in empresa.lower():
        empresa = "Empresa Confidencial"
        
    return empresa


# 🧹 LIMPIEZA DE DESCRIPCIÓN BREVE (Corte por secciones para evitar duplicados)
def limpiar_descripcion_computrabajo(texto_sin_cabecera):
    if not texto_sin_cabecera:
        return "Descripción no disponible."
    
    texto_limpio = normalizar_puntuacion_y_espacios(texto_sin_cabecera)
    
    # 🧹 Limpieza agresiva del "Boilerplate" inicial de salarios y contratos
    patron_basura_inicial = r"^(?:A convenir|Convenio de|Tiempo completo|Tiempo parcial|Por horas|Desde casa|Híbrido|Presencial|Contrato.*?Actividad|Beca/Prácticas|[S/\.\d,\s]*Mensual|\s|-)+"
    texto_limpio = re.sub(patron_basura_inicial, "", texto_limpio, flags=re.IGNORECASE).strip()
    
    return texto_limpio


# 🌀 NORMALIZAR DROPDOWNS PARA EVITAR CRASHES POR DIFERENCIAS DE TEXTO
def normalizar_valor_dropdown(campo, valor):
    if not valor or valor == "-" or str(valor).lower() == "no especificada":
        if campo == "modalidad": return "Presencial"
        if campo == "nivel": return "Práctica"
        if campo == "horario": return "Tiempo Completo"
        if campo == "departamento": return "Lima"
        return None
    
    val_clean = str(valor).strip().lower()
    
    if campo == "plataforma":
        if "computrabajo" in val_clean: return "Computrabajo"
        if "linkedin" in val_clean: return "LinkedIn"
        if "bumeran" in val_clean: return "Bumeran"
        return "LinkedIn"
        
    elif campo == "modalidad":
        if "hibrid" in val_clean or "híbrid" in val_clean: return "Híbrido"
        if "remot" in val_clean: return "Remoto"
        return "Presencial"
        
    elif campo == "nivel":
        if "practi" in val_clean: return "Práctica"
        if "junior" in val_clean or "jr" in val_clean: return "Junior"
        if "trainee" in val_clean: return "Trainee"
        return "Práctica"
        
    elif campo == "horario":
        if "complet" in val_clean or "full" in val_clean: return "Tiempo Completo"
        if "parcial" in val_clean or "part" in val_clean: return "Tiempo Parcial"
        return "Tiempo Completo"
        
    elif campo == "departamento":
        if "lima" in val_clean: return "Lima"
        if "arequipa" in val_clean: return "Arequipa"
        return "Lima"
        
    return valor


# 🟢 SELECTOR DINÁMICO DE DROPDOWN POR JAVASCRIPT (MODIFICADO CON JS CLICK)
def interactuar_dropdown_react(driver, wait, label_id_o_texto, valor_buscar):
    if not valor_buscar:
        return
    try:
        xpath_dropdown = f"//button[contains(., '{label_id_o_texto}') or contains(@id, '{label_id_o_texto}')]"
        dropdown_btn = wait.until(EC.presence_of_element_located((By.XPATH, xpath_dropdown)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_btn)
        time.sleep(0.2)
        driver.execute_script("arguments[0].click();", dropdown_btn)
        time.sleep(0.4)
        
        xpath_opcion = f"//div[@role='option' or @role='menuitem' or contains(@class, 'option')][normalize-space()='{valor_buscar}'] | //span[normalize-space()='{valor_buscar}']"
        opcion_seleccionar = wait.until(EC.presence_of_element_located((By.XPATH, xpath_opcion)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", opcion_seleccionar)
        time.sleep(0.2)
        driver.execute_script("arguments[0].click();", opcion_seleccionar)
        time.sleep(0.2)
        print(f"   ✅ Dropdown exitoso: [{label_id_o_texto}] -> '{valor_buscar}'")
    except Exception as e:
        print(f"   ⚠️ Dropdown [{label_id_o_texto}] omitido o no interactuable.")


# 🚀 FLUJO PRINCIPAL
def ejecutar_pruebas_con_sheets():
    print("📊 Conectando a Google Sheets para extraer vacantes...")
    storage = SheetsHandler()
    
    try:
        client = storage.client
        sheet = client.open("Laboral_AI_Scraper_Data")
        worksheet = sheet.get_worksheet(0) 
        print(f"📋 Pestaña abierta automáticamente: '{worksheet.title}'")
        records = worksheet.get_all_records()
    except Exception as e:
        print(f"❌ Error al conectar o leer el Google Sheet: {e}")
        return

    if not records:
        print("⚠️ No se encontraron filas de ofertas en la hoja seleccionada.")
        return
    
    muestra_ofertas = records[:150]
    print(f"📈 Se cargaron {len(muestra_ofertas)} ofertas reales para la prueba.")

    print("\n🚀 Iniciando navegador Chrome...")
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    wait = WebDriverWait(driver, 150)
    
    try:
        driver.get("https://gestion-comercial-eight.vercel.app/login")
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))).send_keys("data2026@data.com")
        driver.find_element(By.XPATH, "//input[@type='password']").send_keys("1234")
        driver.find_element(By.XPATH, "//button[contains(., 'Entrar al Dashboard')]").click()
        
        menu_ofertas = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(., 'Ofertas Laborales')] | //a[contains(., 'Ofertas Laborales')]")))
        menu_ofertas.click()
        time.sleep(1.0)
    except Exception as e:
        print(f"❌ Error crítico en el Login: {e}")
        driver.quit()
        return

    for idx, fila_original in enumerate(muestra_ofertas, 1):
        fila = {k.strip().lower(): v for k, v in fila_original.items()}
        
        titulo = fila.get("titulo_puesto", "Puesto")
        desc_raw = fila.get("descripcion_breve", "")
        
        # ============================================================================
        # 🗑️ LIMPIEZA Y EXTRACCIÓN (ORDEN CORREGIDO)
        # ============================================================================
        # 1. Purgamos solo la navegación superior básica
        desc_sucia = re.sub(r"Login\s+Crear\s+CV\s+Volver\s+al\s+listado", "", str(desc_raw), flags=re.IGNORECASE).strip()
        desc_sucia = re.sub(r"^.*?Volver al listado", "", desc_sucia, flags=re.IGNORECASE).strip()
        
        # 🏢 EXTRAEMOS LA EMPRESA AQUÍ (Mientras la cabecera sigue viva)
        empresa_extraida = extraer_nombre_empresa(titulo, desc_sucia)
        
        # 2. AHORA SÍ, cortamos la cabecera para limpiar el cuerpo de la descripción
        desc_sucia = re.sub(r"^.*?Descripción de la oferta", "", desc_sucia, flags=re.IGNORECASE | re.DOTALL).strip()
        
        # 3. Purgamos boilerplate legal y de discriminación típico del final
        desc_sucia = re.sub(r"(?:Adecco\s+valora\s+y\s+promueve|En\s+cumplimiento\s+de\s+la\s+ley|Considerando\s+a\s+todos\s+los\s+candidatos\s+sin\s+distinción).*$", "", desc_sucia, flags=re.IGNORECASE | re.DOTALL).strip()
        desc_sucia = re.sub(r"^[-\s|•]+", "", desc_sucia).strip() # Limpia guiones residuales iniciales
        
        print(f"\n============================================================")
        print(f"💼 PROBANDO OFERTA {idx}/{len(muestra_ofertas)}: {titulo}")
        print(f"🏢 Empresa Detectada: '{empresa_extraida}'")
        print(f"============================================================")
        
        try:
            btn_nueva_oferta = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Nueva Oferta External') or contains(., 'Nueva Oferta Externa')]")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_nueva_oferta)
            time.sleep(0.2)
            driver.execute_script("arguments[0].click();", btn_nueva_oferta)
            time.sleep(1.5)
            
            # Formulario
            wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, 'Junior') or contains(@id, 'titulo')]"))).send_keys(titulo)
            driver.find_element(By.XPATH, "//input[contains(@placeholder, 'BBVA') or contains(@id, 'empresa')]").send_keys(empresa_extraida)
            driver.find_element(By.XPATH, "//input[@type='url']").send_keys(fila.get("link_oferta", "https://laboral.ai"))
            
            # Dropdowns
            plataforma_opt = normalizar_valor_dropdown("plataforma", fila.get("plataforma_origen"))
            modalidad_opt = normalizar_valor_dropdown("modalidad", fila.get("modalidad"))
            nivel_opt = normalizar_valor_dropdown("nivel", fila.get("nivel"))
            horario_opt = normalizar_valor_dropdown("horario", fila.get("horario"))
            depto_opt = normalizar_valor_dropdown("departamento", fila.get("departamento"))
            
            interactuar_dropdown_react(driver, wait, "Seleccionar plataforma", plataforma_opt)
            interactuar_dropdown_react(driver, wait, "Seleccionar modalidad", modalidad_opt)
            interactuar_dropdown_react(driver, wait, "Seleccionar nivel", nivel_opt)
            interactuar_dropdown_react(driver, wait, "Seleccionar horario", horario_opt)
            interactuar_dropdown_react(driver, wait, "Seleccionar departamento", depto_opt)
            
            # Area / Categoría
            area_raw = fila.get("arrea categoria") or fila.get("area_categoria") or "Marketing"
            input_area = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'Marketing')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_area)
            time.sleep(0.2)
            input_area.send_keys(area_raw)
            
            # ============================================================================
            # 🧼 1. EXTRACTOR Y LIMPIADOR DE DESCRIPCIÓN BREVE (CORTE PERFECTO)
            # ============================================================================
            # ============================================================================
            # 🧼 1. EXTRACTOR Y LIMPIADOR DE DESCRIPCIÓN BREVE (CORTE PERFECTO)
            # ============================================================================
            # Ampliamos la red para atrapar cualquier variación de subtítulos
            patrones_corte_desc = [
                r"¿?\s*Qué buscamos\b[^\?]*\??", 
                r"¿?\s*Cuáles ser(?:án|ían) tus\b[^\?]*\??",
                r"¿?\s*Qué necesitas\b[^\?]*\??",
                r"¿?\s*Qué requisitos\b[^\?]*\??",
                r"\b(?:Requisitos|Funciones|Perfil|Beneficios)\b\s*[:\-\.]",
                r"¿?\s*Cuál es tu reto\s*\??"
            ]
            
            desc_limpia = limpiar_descripcion_computrabajo(desc_sucia)
            
            # Cortamos el texto exactamente donde empieza el primer subtítulo
            for patron in patrones_corte_desc:
                match_corte = re.search(patron, desc_limpia, flags=re.IGNORECASE)
                if match_corte:
                    desc_limpia = desc_limpia[:match_corte.start()].strip()
                    break 
            
            # 🛡️ Fallback: Si no encontró subtítulos y el texto sigue siendo gigante (>500 chars)
            # extraemos solo las primeras 3 oraciones para mantenerlo "Breve".
            if len(desc_limpia) > 500 or len(desc_limpia) < 30:
                oraciones = re.split(r'(?<=[.!?])\s+', normalizar_puntuacion_y_espacios(desc_limpia))
                desc_limpia = " ".join(oraciones[:3]).strip()
                if not desc_limpia.endswith("."):
                    desc_limpia += "."
            
            textarea_desc = driver.find_element(By.XPATH, "//textarea[contains(@placeholder, 'Describe brevemente')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", textarea_desc)
            time.sleep(0.2)
            # Asegurar límite de caracteres por si acaso
            textarea_desc.send_keys(desc_limpia[:1500])
            
            # ============================================================================
            # 🧠 2. EXTRACTOR FLEXIBLE DE REQUISITOS (SEGMENTADO INTELIGENTE)
            # ============================================================================
            requisitos_lista = []
            
            patron_inicio_req = r"(?:Requisitos\s*:|¿?\s*Qué requisitos necesitas\s*\??|¿?\s*Qué necesitas\s*\??|¿?\s*Qué buscamos de ti[^\?]*\??)"
            patron_fin_req = r"(?:¿?\s*Cuáles? ser(?:ía|á)n? tus (?:roles|funciones|retos?)\s*\??|Funciones principales\s*:|¿?\s*Qué ofrecemos\s*\??|Ofrecemos\s*:|¿?\s*Cuál es tu horario\s*\??|Requerimientos|$)"
            
            match_req = re.search(rf"{patron_inicio_req}(.*?)(?={patron_fin_req})", desc_sucia, flags=re.IGNORECASE | re.DOTALL)
            
            if match_req:
                bloque_req = match_req.group(1).strip()
                frases_req = segmentar_bloque_unido(bloque_req)
                
                for frase in frases_req:
                    tipo = "Deseable" if any(w in frase.lower() for w in ["deseable", "preferible", "opcional"]) else "Indispensable"
                    requisitos_lista.append({"texto": frase, "tipo": tipo})

            if not requisitos_lista:
                print("   ⚠️ Requisitos no extraídos. Usando plantilla de respaldo para:", area_raw)
                requisitos_lista = [
                    {"texto": f"Estudios en {area_raw} o carreras afines.", "tipo": "Indispensable"},
                    {"texto": "Conocimiento y manejo de herramientas digitales del sector.", "tipo": "Indispensable"},
                    {"texto": "Experiencia previa o proyectos relacionados al puesto (Deseable).", "tipo": "Deseable"}
                ]

            # ============================================================================
            # 🎁 3. EXTRACTOR FLEXIBLE DE BENEFICIOS (SIN SPAM LEGAL)
            # ============================================================================
            # ============================================================================
            # 🎁 3. EXTRACTOR FLEXIBLE DE BENEFICIOS (SIN SPAM LEGAL)
            # ============================================================================
            beneficios_lista = []
            
            # Patrones de inicio expandidos
            patron_inicio_ben = r"(?:¿?\s*Qué ofrecemos\s*\??|Ofrecemos\s*:|Beneficios\s*:|Te ofrecemos\s*:)"
            
            # ⛔ Patrones de fin expandidos (Frena al detectar "Requerimientos", inclusión, o despedidas)
            patron_fin_ben = r"(?:Requerimientos|Educación mínima|Edad:|Palabras clave:|Adecco valora|En\s+[A-Za-z]+\s+estamos\s+comprometidos|¡Atrévete a un cambio|Únete a nuestr|Postula|No especificados|$)"
            
            match_ben = re.search(rf"{patron_inicio_ben}(.*?)(?={patron_fin_ben})", desc_sucia, flags=re.IGNORECASE | re.DOTALL)
            
            if match_ben:
                bloque_ben = match_ben.group(1).strip()
                # Quitamos frases comunes que no son beneficios reales antes de segmentar
                bloque_ben = re.sub(r"(?:La oportunidad de crecer.*|Forma parte de nuestra.*|Postula aquí.*)", "", bloque_ben, flags=re.IGNORECASE).strip()
                
                lineas_ben = segmentar_bloque_unido(bloque_ben)
                
                for linea in lineas_ben:
                    if len(linea) > 4:  # Evitar viñetas vacías
                        beneficios_lista.append(f"• {linea}")

            # 🛡️ Fallback: Si no hay beneficios explícitos, pero el campo es obligatorio
            if beneficios_lista:
                beneficios_final_txt = "\n".join(beneficios_lista[:6]) # Máximo 6 beneficios para no saturar
            else:
                beneficios_final_txt = "• Oportunidad de desarrollo profesional.\n• Excelente ambiente de trabajo.\n• Aprendizaje continuo."

            textarea_ben = driver.find_element(By.XPATH, "//textarea[contains(@placeholder, 'Seguro médico') or contains(., 'Beneficios')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", textarea_ben)
            time.sleep(0.2)
            textarea_ben.send_keys(beneficios_final_txt)
            
            # ============================================================================
            # 🛠️ RELLENAR REQUISITOS (MODIFICADO: BÚSQUEDA DEL ÚLTIMO ELEMENTO VISIBLE)
            # ============================================================================
            for r_idx, req in enumerate(requisitos_lista, 1):
                btn_agregar = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Agregar requisito')]")))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_agregar)
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", btn_agregar)
                time.sleep(0.5)
                
                inputs_req = driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'experiencia en Python')]")
                ultimo_input = inputs_req[-1]
                
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", ultimo_input)
                time.sleep(0.2)
                
                # Clic forzado por si hay algún panel transparente superpuesto
                driver.execute_script("arguments[0].click();", ultimo_input)
                ultimo_input.send_keys(req.get("texto", "Requisito general"))
                time.sleep(0.2)
                
                tipo_req = req.get("tipo", "Indispensable").strip().capitalize()
                if tipo_req == "Deseable":
                    print(f"   🔄 Cambiando requisito [{r_idx}] a: 'Deseable'")
                    botones_tipo = driver.find_elements(By.XPATH, "//button[contains(., 'Indispensable') or contains(., 'Deseable')]")
                    ultimo_boton_tipo = botones_tipo[-1]
                    
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", ultimo_boton_tipo)
                    time.sleep(0.2)
                    driver.execute_script("arguments[0].click();", ultimo_boton_tipo)
                    time.sleep(0.3)
                    
                    xpath_deseable = "//div[@role='option' or @role='menuitem'][normalize-space()='Deseable'] | //span[normalize-space()='Deseable']"
                    opciones_deseable = driver.find_elements(By.XPATH, xpath_deseable)
                    
                    # 💡 EL TRUCO: Buscar desde el último hacia atrás y validar que esté VISIBLE
                    for opcion in reversed(opciones_deseable):
                        if opcion.is_displayed():
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", opcion)
                            time.sleep(0.2)
                            driver.execute_script("arguments[0].click();", opcion)
                            break
                    time.sleep(0.2)
            
            print(f"\n👉 [FILA {idx}] LLENADA CON ÉXITO.")
            
            # 1. Hacemos clic en el botón azul para GUARDAR la oferta
            btn_crear = driver.find_element(By.XPATH, "//button[contains(., 'Crear Oferta Externa')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_crear)
            time.sleep(0.2)
            driver.execute_script("arguments[0].click();", btn_crear)
            
            # Le damos un par de segundos para que la página procese el guardado y cierre el modal/vuelva a la lista
            time.sleep(2.5) 
            
            # 2. Lógica para pausar cada 5 iteraciones
            if idx % 5 == 0:
                print("\n============================================================")
                input(f"🛑 [PAUSA DE REVISIÓN] Se han guardado {idx} ofertas. Revisa en tu dashboard que todo esté bien y presiona [ENTER] aquí para continuar...")
                print("============================================================\n")
            
        except Exception as row_error:
            print(f"❌ Error procesando fila {idx}: {row_error}")
            driver.refresh()
            time.sleep(2.0)

    print("\n🏁 Simulación finalizada.")

if __name__ == "__main__":
    ejecutar_pruebas_con_sheets()