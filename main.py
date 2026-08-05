"""
Módulo: main.py (Orquestador principal compatible con Streamlit y Hugging Face)
"""
import sys
import os
import time
import hashlib
import json
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

# Agregar raíz del proyecto al path para imports absolutos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importaciones de NLP y Storage
from nlp.text_cleaner import TextCleaner
from nlp.ai_extractor import AIExtractor
from storage.sheets_handler import SheetsHandler, SheetsHandlerSimulado

# Importaciones de Scrapers (Nombres corregidos)
from scrapers.computrabajo_scraper import ComputrabajoScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.bumeran_scraper import BumeranScraper
from scrapers.indeed_scraper import IndeedScraperPlaywright

# ============================================================
# CAPA 1: FILTRO RÁPIDO DE TÍTULOS
# ============================================================
def es_titulo_relevante(titulo: str, puesto_buscado: str) -> bool:
    titulo_lower = titulo.lower().strip()
    puesto_lower = puesto_buscado.lower().strip()
    
    if puesto_lower in titulo_lower:
        return True
        
    genericos = ["practicante", "pasante", "trainee", "intern", "prácticas", "practicas", "estudiante", "apoyo"]
    if any(gen in titulo_lower for gen in genericos):
        return True
        
    return False

# ============================================================
# CAPA 2: VALIDACIÓN SEMÁNTICA PROFUNDA
# ============================================================
def validar_contenido_semantico(oferta: dict, puesto: str) -> bool:
    DICCIONARIO_AREAS = {
        "marketing": ["marketing", "branding", "digital", "seo", "sem", "growth", "comunicaciones", "publicidad", "social media", "community manager", "trade marketing", "contenido", "creativo", "diseño"],
        "datos": ["data", "datos", "analytics", "analista de datos", "bi", "business intelligence", "sql", "power bi", "powerbi", "python", "excel", "dashboard", "tableau", "reporting"]
    }
    
    texto = oferta.get("texto_crudo", "").lower()
    titulo = oferta.get("titulo_puesto", "").lower()
    puesto_normalizado = puesto.lower()
    
    palabras_clave = [puesto_normalizado]
    if "marketing" in puesto_normalizado:
        palabras_clave.extend(DICCIONARIO_AREAS["marketing"])
    elif any(x in puesto_normalizado for x in ["dato", "data", "analyst"]):
        palabras_clave.extend(DICCIONARIO_AREAS["datos"])
    else:
        palabras_clave.extend(puesto_normalizado.split())
        
    palabras_clave = list(set(palabras_clave))
    
    return any(palabra in titulo for palabra in palabras_clave) or \
           any(palabra in texto for palabra in palabras_clave)

# ============================================================
# PROCESAMIENTO NLP DE UNA OFERTA
# ============================================================
def procesar_oferta_con_nlp(
    oferta: dict,
    nombre_plataforma: str,
    lugar: str,
    cleaner: TextCleaner,
    extractor: AIExtractor
) -> Optional[Dict]:
    texto_crudo = oferta.get("texto_crudo", "")
    titulo_oferta = oferta.get("titulo_puesto", "No especificado")
    
    if not texto_crudo or len(texto_crudo) < 50:
        return None
        
    try:
        texto_limpio = cleaner.limpiar_texto(texto_crudo)
        datos_extraidos = extractor.extraer_datos_oferta(texto_limpio)
        
        id_unico = hashlib.md5(f"{nombre_plataforma}_{oferta.get('link_oferta', '')}".encode()).hexdigest()[:12]
        puesto_normalizado = oferta.get("puesto_buscado", "").lower()
        categoria_hoja = "Marketing" if "marketing" in puesto_normalizado else "Data & Analytics"
        
        return {
            "id_oferta": f"{nombre_plataforma[:3].upper()}-{id_unico}",
            "fecha_scraping": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "plataforma_origen": nombre_plataforma,
            "link_oferta": oferta.get("link_oferta", ""),
            "titulo_puesto": titulo_oferta if titulo_oferta else datos_extraidos.get("titulo_puesto", "No especificado"),
            "empresa": datos_extraidos.get("empresa", "No especificada"),
            "modalidad": datos_extraidos.get("modalidad", "Presencial"),
            "disponible_hasta": "-",
            "nivel": datos_extraidos.get("nivel", "Practicante"),
            "horario": datos_extraidos.get("horario", "Tiempo Completo"),
            "departamento": lugar.capitalize(),
            "area_categoria": categoria_hoja,
            "descripcion_breve": texto_limpio[:3000],
            "requisitos": json.dumps(datos_extraidos.get("requisitos", []), ensure_ascii=False),
            "beneficios": datos_extraidos.get("beneficios", "No especificados")
        }
    except Exception as e:
        logger.error(f"❌ Error procesando oferta con NLP: {e}")
        return None

# ============================================================
# EJECUCIÓN DE UN SCRAPER INDIVIDUAL
# ============================================================
def ejecutar_scraper(
    scraper,
    nombre: str,
    puesto: str,
    lugar: str,
    limite_ofertas: int,
    es_playwright: bool = False
) -> List[Dict]:
    logger.info(f"\n📌 RASTREANDO: {nombre}")
    logger.info("-" * 50)
    
    try:
        if es_playwright:
            ofertas_crudas = scraper.recolectar_ofertas_sync(
                puesto=puesto,
                lugar=lugar,
                limite_ofertas=limite_ofertas,
                filtro_relevancia_cb=es_titulo_relevante
            )
        else:
            ofertas_crudas = scraper.recolectar_ofertas(
                url_semilla="",
                limite_ofertas=limite_ofertas,
                puesto=puesto,
                lugar=lugar,
                filtro_relevancia_cb=es_titulo_relevante
            )
            
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
        try:
            scraper.cerrar_navegador()
        except Exception as e:
            logger.debug(f"⚠️ Aviso al cerrar navegador de {nombre}: {e}")

# ============================================================
# PIPELINE PRINCIPAL (Compatible con Streamlit)
# ============================================================
def ejecutar_pipeline(
    puesto: str = "practicante de datos",
    lugar: str = "lima",
    limite_ofertas: int = 10,
    usar_bumeran: bool = True,
    usar_computrabajo: bool = True,
    usar_linkedin: bool = False,
    usar_indeed: bool = False,
    usar_nlp: bool = True,
    progress_callback=None
) -> Dict:
    
    logger.info("=" * 60)
    logger.info("🏁 INICIANDO PIPELINE DE AUTOMATIZACIÓN - LABORAL AI")
    logger.info(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    # 1. Inicialización pesada (se hace UNA sola vez)
    cleaner = TextCleaner()
    extractor = AIExtractor()
    
    # 2. Inicialización segura de Storage
    try:
        storage = SheetsHandler()
        if storage.sheet is None:
            logger.info("🧪 Usando modo simulación (Sin credenciales de Google)")
            storage = SheetsHandlerSimulado()
    except Exception as e:
        logger.warning(f"⚠️ No se pudo conectar a Google Sheets: {e}")
        storage = SheetsHandlerSimulado()
        
    # 3. Configurar scrapers activos
    scrapers_config = []
    if usar_computrabajo:
        scrapers_config.append({'scraper': ComputrabajoScraper(), 'nombre': 'Computrabajo', 'es_playwright': False})
    if usar_bumeran:
        scrapers_config.append({'scraper': BumeranScraper(), 'nombre': 'Bumeran', 'es_playwright': False})
    if usar_linkedin:
        scrapers_config.append({'scraper': LinkedInScraper(), 'nombre': 'LinkedIn', 'es_playwright': False})
    if usar_indeed:
        scrapers_config.append({'scraper': IndeedScraperPlaywright(), 'nombre': 'Indeed', 'es_playwright': True})
        
    if not scrapers_config:
        return {'success': False, 'error': 'No hay scrapers activados', 'total_ofertas': 0}
        
    total_ofertas_guardadas = 0
    resultados_por_scraper = {}
    todos_los_payloads = []
    
    try:
        for idx, config in enumerate(scrapers_config, 1):
            scraper = config['scraper']
            nombre = config['nombre']
            es_playwright = config['es_playwright']
            
            if progress_callback:
                progress_callback(idx, len(scrapers_config), f"Ejecutando {nombre}...")
                
            ofertas_validadas = ejecutar_scraper(scraper, nombre, puesto, lugar, limite_ofertas, es_playwright)
            
            if not ofertas_validadas:
                resultados_por_scraper[nombre] = {'extraidas': 0, 'guardadas': 0}
                continue
                
            # Procesar con NLP
            payloads = []
            for oferta in ofertas_validadas:
                oferta['puesto_buscado'] = puesto
                if usar_nlp:
                    payload = procesar_oferta_con_nlp(oferta, nombre, lugar, cleaner, extractor)
                    if payload:
                        payloads.append(payload)
                else:
                    payloads.append({
                        "id_oferta": f"{nombre[:3].upper()}-{hashlib.md5(oferta.get('link_oferta', '').encode()).hexdigest()[:12]}",
                        "fecha_scraping": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "plataforma_origen": nombre,
                        "link_oferta": oferta.get("link_oferta", ""),
                        "titulo_puesto": oferta.get("titulo_puesto", "No especificado"),
                        "empresa": "No especificada", "modalidad": "Presencial", "disponible_hasta": "-",
                        "nivel": "Practicante", "horario": "Tiempo Completo", "departamento": lugar.capitalize(),
                        "area_categoria": "General", "descripcion_breve": oferta.get("texto_crudo", "")[:3000],
                        "requisitos": "[]", "beneficios": "No especificados"
                    })
                    
            # Guardar en Sheets
            stats = storage.verificar_y_guardar(
                ofertas_del_scraper=payloads,
                nombre_scraper=nombre,
                puesto=puesto,
                lugar=lugar
            )
            
            resultados_por_scraper[nombre] = {
                'extraidas': len(ofertas_validadas),
                'guardadas': stats.get('guardadas', 0),
                'duplicadas': stats.get('duplicadas', 0),
                'errores': stats.get('errores', 0)
            }
            
            total_ofertas_guardadas += stats.get('guardadas', 0)
            todos_los_payloads.extend(payloads)
            
            logger.info(f"✅ {nombre}: {stats.get('guardadas', 0)} nuevas, {stats.get('duplicadas', 0)} duplicadas")
            
        if progress_callback:
            progress_callback(len(scrapers_config), len(scrapers_config), "✅ Pipeline completado")
            
    except Exception as e:
        logger.critical(f"💥 Falla general: {e}")
        return {'success': False, 'error': str(e), 'total_ofertas': total_ofertas_guardadas}
        
    elapsed = time.time() - start_time
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 INFORME FINAL")
    logger.info("=" * 60)
    logger.info(f"   📌 Total guardadas: {total_ofertas_guardadas}")
    logger.info(f"   ⏱️  Tiempo: {elapsed:.2f} segundos")
    logger.info("=" * 60)
    
    return {
        'success': True,
        'total_ofertas': total_ofertas_guardadas,
        'resultados_por_scraper': resultados_por_scraper,
        'tiempo_ejecucion': elapsed,
        'payloads': todos_los_payloads
    }

# ============================================================
# EJECUCIÓN DIRECTA (para testing desde consola)
# ============================================================
if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="INFO")
    
    # ⚠️ IMPORTANTE: Usa un límite bajo (ej. 5) para pruebas rápidas en local
    resultados = ejecutar_pipeline(
        puesto="practicante de datos",
        lugar="lima",
        limite_ofertas=50,  # <--- Cambia esto a 50 o 100 para producción
        usar_bumeran=True,
        usar_computrabajo=True,
        usar_linkedin=False,
        usar_indeed=False,
        usar_nlp=True
    )
    
    if resultados['success']:
        print(f"\n✅ Pipeline completado: {resultados['total_ofertas']} ofertas guardadas")
    else:
        print(f"\n❌ Error: {resultados.get('error')}")