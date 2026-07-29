"""
Módulo: main.py (Con límites dinámicos por portal y optimizado)
"""
import sys, os, time, hashlib, json
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from nlp.text_cleaner import TextCleaner
from nlp.ai_extractor import AIExtractor
from storage.sheets_handler import SheetsHandler, SheetsHandlerSimulado
from scrapers.computrabajo_scraper import ComputrabajoScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.bumeran_scraper import BumeranScraper

def es_titulo_relevante(titulo: str, puesto_buscado: str) -> bool:
    titulo_lower, puesto_lower = titulo.lower().strip(), puesto_buscado.lower().strip()
    if puesto_lower in titulo_lower: return True
    return any(gen in titulo_lower for gen in ["practicante", "pasante", "trainee", "intern", "prácticas", "estudiante", "apoyo"])

def validar_contenido_semantico(oferta: dict, puesto: str) -> bool:
    DICCIONARIO_AREAS = {
        "marketing": ["marketing", "branding", "digital", "seo", "sem", "growth", "comunicaciones", "publicidad", "social media"],
        "datos": ["data", "datos", "analytics", "analista de datos", "bi", "business intelligence", "sql", "power bi", "python", "excel", "dashboard"]
    }
    texto, titulo = oferta.get("texto_crudo", "").lower(), oferta.get("titulo_puesto", "").lower()
    puesto_normalizado = puesto.lower()
    palabras_clave = [puesto_normalizado]
    if "marketing" in puesto_normalizado: palabras_clave.extend(DICCIONARIO_AREAS["marketing"])
    elif any(x in puesto_normalizado for x in ["dato", "data", "analyst"]): palabras_clave.extend(DICCIONARIO_AREAS["datos"])
    else: palabras_clave.extend(puesto_normalizado.split())
    return any(p in titulo for p in palabras_clave) or any(p in texto for p in palabras_clave)

def procesar_oferta_con_nlp(oferta: dict, nombre_plataforma: str, lugar: str, cleaner: TextCleaner, extractor: AIExtractor) -> Optional[Dict]:
    texto_crudo, titulo_oferta = oferta.get("texto_crudo", ""), oferta.get("titulo_puesto", "No especificado")
    if not texto_crudo or len(texto_crudo) < 50: return None
    
    try:
        texto_limpio = cleaner.limpiar_texto(texto_crudo)
        datos_extraidos = extractor.extraer_datos_oferta(texto_limpio)
        id_unico = hashlib.md5(f"{nombre_plataforma}_{oferta.get('link_oferta', '')}".encode()).hexdigest()[:12]
        puesto_normalizado = oferta.get("puesto_buscado", "").lower()
        categoria_hoja = "Marketing" if "marketing" in puesto_normalizado else "Data & Analytics"
        
        reqs_raw = datos_extraidos.get("requisitos", [])
        reqs_text = [r.get("texto", "") for r in reqs_raw if r.get("texto")]
        requisitos_comprimidos = "; ".join(reqs_text[:8])
        
        bens_raw = datos_extraidos.get("beneficios", "")
        bens_list = [b.strip("• \n\r") for b in bens_raw.split("\n") if b.strip() and len(b.strip()) > 5]
        beneficios_comprimidos = "; ".join(bens_list[:5])
        
        return {
            "id_oferta": f"{nombre_plataforma[:3].upper()}-{id_unico}",
            "fecha_scraping": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "plataforma_origen": nombre_plataforma,
            "link_oferta": oferta.get("link_oferta", ""),
            "titulo_puesto": titulo_oferta if titulo_oferta else datos_extraidos.get("titulo_puesto", "No especificado"),
            "empresa": datos_extraidos.get("empresa", "No especificada"),
            "modalidad": datos_extraidos.get("modalidad", "Presencial"),
            "disponible_hasta": "-",
            "horario": datos_extraidos.get("horario", "Tiempo Completo"),
            "departamento": lugar.capitalize(),
            "area_categoria": categoria_hoja,
            "descripcion_breve": texto_limpio[:2000],
            "requisitos": requisitos_comprimidos if requisitos_comprimidos else "No especificados",
            "beneficios": beneficios_comprimidos if beneficios_comprimidos else "No especificados"
        }
    except Exception as e:
        logger.error(f"❌ Error NLP: {e}")
        return None

def ejecutar_scraper(scraper, nombre: str, puesto: str, lugar: str, limite_ofertas: int, es_playwright: bool = False) -> List[Dict]:
    logger.info(f"\n📌 RASTREANDO: {nombre}\n" + "-" * 50)
    try:
        if es_playwright:
            ofertas_crudas = scraper.recolectar_ofertas_sync(puesto=puesto, lugar=lugar, limite_ofertas=limite_ofertas, filtro_relevancia_cb=es_titulo_relevante)
        else:
            ofertas_crudas = scraper.recolectar_ofertas(url_semilla="", limite_ofertas=limite_ofertas, puesto=puesto, lugar=lugar, filtro_relevancia_cb=es_titulo_relevante)
        
        if not ofertas_crudas:
            logger.warning(f"⚠️ No se extrajeron ofertas de {nombre}.")
            return []
            
        ofertas_validadas = [ofr for ofr in ofertas_crudas if validar_contenido_semantico(ofr, puesto)]
        logger.info(f"✅ Ofertas purificadas: {len(ofertas_validadas)} de {len(ofertas_crudas)}")
        return ofertas_validadas
    except Exception as e:
        logger.error(f"❌ Error en portal {nombre}: {e}")
        return []
    finally:
        try: scraper.cerrar_navegador()
        except: pass

def ejecutar_pipeline(puesto: str = None, lugar: str = None, 
                     limites_por_portal: dict = None, # ✅ NUEVO: Límites dinámicos
                     usar_bumeran: bool = True, usar_computrabajo: bool = True, 
                     usar_linkedin: bool = True, usar_indeed: bool = False,  
                     usar_nlp: bool = True, progress_callback=None) -> Dict:
    
    logger.info("=" * 60 + "\n🏁 INICIANDO PIPELINE DE AUTOMATIZACIÓN - LABORAL AI\n" + "=" * 60)
    start_time = time.time()
    cleaner, extractor = TextCleaner(), AIExtractor()
    
    try: storage = SheetsHandler()
    except: storage = SheetsHandlerSimulado()
    
    if puesto is None or lugar is None:
        logger.info("📋 Leyendo configuración desde Config_Busquedas...")
        busquedas_activas = storage.obtener_busquedas_activas()
        if not busquedas_activas:
            return {'success': False, 'error': 'No hay búsquedas activas', 'total_ofertas': 0}
        puesto, lugar = busquedas_activas[0]['puesto'], busquedas_activas[0]['lugar']
        logger.info(f"🎯 Búsqueda detectada: {puesto} en {lugar}")
    
    # Valores por defecto si no se proporcionan
    if limites_por_portal is None:
        limites_por_portal = {"Computrabajo": 15, "Bumeran": 15, "LinkedIn": 15, "Indeed": 15}
    
    scrapers_config = []
    if usar_computrabajo: scrapers_config.append({'scraper': ComputrabajoScraper(), 'nombre': 'Computrabajo', 'es_playwright': False})
    if usar_bumeran: scrapers_config.append({'scraper': BumeranScraper(), 'nombre': 'Bumeran', 'es_playwright': False})
    if usar_linkedin: scrapers_config.append({'scraper': LinkedInScraper(), 'nombre': 'LinkedIn', 'es_playwright': False})
    
    if not scrapers_config: return {'success': False, 'error': 'No hay scrapers activados', 'total_ofertas': 0}
    
    total_ofertas_guardadas, resultados_por_scraper, todos_los_payloads = 0, {}, []
    
    try:
        for idx, config in enumerate(scrapers_config, 1):
            if progress_callback: progress_callback(idx, len(scrapers_config), f"Ejecutando {config['nombre']}...")
            
            # ✅ AQUÍ SE USA EL LÍMITE ESPECÍFICO PARA CADA PORTAL
            limite_actual = limites_por_portal.get(config['nombre'], 15)
            
            ofertas_validadas = ejecutar_scraper(config['scraper'], config['nombre'], puesto, lugar, limite_actual, config['es_playwright'])
            if not ofertas_validadas:
                resultados_por_scraper[config['nombre']] = {'extraidas': 0, 'guardadas': 0}
                continue
                
            payloads = []
            for oferta in ofertas_validadas:
                oferta['puesto_buscado'] = puesto
                if usar_nlp:
                    payload = procesar_oferta_con_nlp(oferta, config['nombre'], lugar, cleaner, extractor)
                    if payload: payloads.append(payload)
                else:
                    payloads.append({"id_oferta": f"{config['nombre'][:3].upper()}-x", "fecha_scraping": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "plataforma_origen": config['nombre'], "link_oferta": oferta.get("link_oferta", ""), "titulo_puesto": oferta.get("titulo_puesto", ""), "empresa": "N/A", "modalidad": "N/A", "disponible_hasta": "-", "horario": "N/A", "departamento": lugar.capitalize(), "area_categoria": "General", "descripcion_breve": oferta.get("texto_crudo", "")[:2000], "requisitos": "N/A", "beneficios": "N/A"})
            
            stats = storage.verificar_y_guardar(ofertas_del_scraper=payloads, nombre_scraper=config['nombre'], puesto=puesto, lugar=lugar)
            resultados_por_scraper[config['nombre']] = {'extraidas': len(ofertas_validadas), 'guardadas': stats.get('guardadas', 0), 'duplicadas': stats.get('duplicadas', 0), 'errores': stats.get('errores', 0)}
            total_ofertas_guardadas += stats.get('guardadas', 0)
            todos_los_payloads.extend(payloads)
            logger.info(f"✅ {config['nombre']}: {stats.get('guardadas', 0)} nuevas")
            
        if progress_callback: progress_callback(len(scrapers_config), len(scrapers_config), "✅ Pipeline completado")
    except Exception as e:
        logger.critical(f"💥 Falla general: {e}")
        return {'success': False, 'error': str(e), 'total_ofertas': total_ofertas_guardadas}
        
    logger.info(f"\n📊 Total guardadas: {total_ofertas_guardadas} | ⏱️ Tiempo: {time.time() - start_time:.2f}s")
    return {'success': True, 'total_ofertas': total_ofertas_guardadas, 'resultados_por_scraper': resultados_por_scraper, 'tiempo_ejecucion': time.time() - start_time, 'payloads': todos_los_payloads}

if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="INFO")
    
    # ✅ CONFIGURACIÓN DINÁMICA DE LÍMITES POR PORTAL
    limites_dinamicos = {
        "Computrabajo": 80,  # Ejemplo: sacar hasta 20 de aquí
        "Bumeran": 80,       # Ejemplo: sacar hasta 15 de aquí
        "LinkedIn": 80,      # Ejemplo: sacar hasta 10 de aquí (LinkedIn es lento)
        "Indeed": 0          # Desactivado
    }
    
    resultados = ejecutar_pipeline(
        puesto=None, lugar=None, 
        limites_por_portal=limites_dinamicos, # <-- Se pasa el diccionario
        usar_bumeran=True, usar_computrabajo=True, usar_linkedin=True,
        usar_indeed=False, usar_nlp=True
    )
    
    if resultados['success']: print(f"\n✅ Pipeline completado: {resultados['total_ofertas']} ofertas guardadas")
    else: print(f"\n❌ Error: {resultados.get('error')}")
