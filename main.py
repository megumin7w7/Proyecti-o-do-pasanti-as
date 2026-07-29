"""
Módulo: main.py (Optimizado con Bucles Invertidos para velocidad)
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

def ejecutar_pipeline(limites_por_portal: dict = None,
                     usar_bumeran: bool = True, usar_computrabajo: bool = True, 
                     usar_linkedin: bool = True, usar_indeed: bool = False,  
                     usar_nlp: bool = True) -> Dict:
    
    logger.info("=" * 60 + "\n🏁 INICIANDO PIPELINE DE AUTOMATIZACIÓN - LABORAL AI\n" + "=" * 60)
    start_time = time.time()
    cleaner, extractor = TextCleaner(), AIExtractor()
    
    try: storage = SheetsHandler()
    except: storage = SheetsHandlerSimulado()
    
    # 1. OBTENER TODAS LAS BÚSQUEDAS
    busquedas_a_ejecutar = storage.obtener_busquedas_activas()
    if not busquedas_a_ejecutar:
        return {'success': False, 'error': 'No hay búsquedas activas en Config_Busquedas', 'total_ofertas': 0}
    
    logger.info(f"🎯 Se ejecutarán {len(busquedas_a_ejecutar)} búsqueda(s):")
    for i, b in enumerate(busquedas_a_ejecutar, 1):
        logger.info(f"   {i}. {b['puesto']} en {b['lugar']}")
    
    if limites_por_portal is None:
        limites_por_portal = {"Computrabajo": 20, "Bumeran": 20, "LinkedIn": 20}
    
    total_ofertas_guardadas = 0
    resultados_por_scraper = {}
    todos_los_payloads = []
    
    # 2. CONFIGURAR PORTALES
    portales = []
    if usar_computrabajo: portales.append({'scraper': ComputrabajoScraper(), 'nombre': 'Computrabajo'})
    if usar_bumeran: portales.append({'scraper': BumeranScraper(), 'nombre': 'Bumeran'})
    if usar_linkedin: portales.append({'scraper': LinkedInScraper(), 'nombre': 'LinkedIn'})
    
    if not portales:
        return {'success': False, 'error': 'No hay portales activados', 'total_ofertas': 0}

    try:
        # 🚀 ESTRATEGIA CLAVE: BUCLE EXTERNO POR PORTAL, INTERNO POR BÚSQUEDA
        for portal in portales:
            scraper = portal['scraper']
            nombre_portal = portal['nombre']
            limite_portal = limites_por_portal.get(nombre_portal, 20)
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🌐 INICIANDO NAVEGADOR PARA: {nombre_portal}")
            logger.info(f"{'='*60}")
            
            # ABRIR NAVEGADOR UNA SOLA VEZ POR PORTAL
            scraper.iniciar_navegador(headless=True)
            
            try:
                for busqueda in busquedas_a_ejecutar:
                    puesto = busqueda['puesto']
                    lugar = busqueda['lugar']
                    
                    logger.info(f"\n🔍 Buscando: '{puesto}' en '{lugar}' (Límite: {limite_portal})")
                    
                    # Ejecutar scraping (el scraper usa self.page que ya está abierto)
                    try:
                        ofertas_crudas = scraper.recolectar_ofertas(
                            url_semilla="", 
                            limite_ofertas=limite_portal, 
                            puesto=puesto, 
                            lugar=lugar, 
                            filtro_relevancia_cb=es_titulo_relevante
                        )
                    except Exception as e:
                        logger.error(f"❌ Fallo en {nombre_portal} para '{puesto}': {e}")
                        continue
                    
                    if not ofertas_crudas:
                        logger.warning(f"⚠️ 0 ofertas extraídas de {nombre_portal} para '{puesto}'")
                        continue
                    
                    ofertas_validadas = [ofr for ofr in ofertas_crudas if validar_contenido_semantico(ofr, puesto)]
                    logger.info(f"✅ Ofertas purificadas: {len(ofertas_validadas)} de {len(ofertas_crudas)}")
                    
                    # Procesar y guardar
                    payloads = []
                    for oferta in ofertas_validadas:
                        oferta['puesto_buscado'] = puesto
                        if usar_nlp:
                            payload = procesar_oferta_con_nlp(oferta, nombre_portal, lugar, cleaner, extractor)
                            if payload: payloads.append(payload)
                        else:
                            payloads.append({"id_oferta": f"{nombre_portal[:3].upper()}-x", "fecha_scraping": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "plataforma_origen": nombre_portal, "link_oferta": oferta.get("link_oferta", ""), "titulo_puesto": oferta.get("titulo_puesto", ""), "empresa": "N/A", "modalidad": "N/A", "disponible_hasta": "-", "horario": "N/A", "departamento": lugar.capitalize(), "area_categoria": "General", "descripcion_breve": oferta.get("texto_crudo", "")[:2000], "requisitos": "N/A", "beneficios": "N/A"})
                    
                    stats = storage.verificar_y_guardar(ofertas_del_scraper=payloads, nombre_scraper=nombre_portal, puesto=puesto, lugar=lugar)
                    
                    key_res = f"{nombre_portal}_{puesto.replace(' ', '_')}_{lugar}"
                    resultados_por_scraper[key_res] = {'extraidas': len(ofertas_validadas), 'guardadas': stats.get('guardadas', 0)}
                    
                    total_ofertas_guardadas += stats.get('guardadas', 0)
                    todos_los_payloads.extend(payloads)
                    logger.info(f"💾 {nombre_portal}: {stats.get('guardadas', 0)} nuevas guardadas para '{puesto}'")
                    
            finally:
                # CERRAR NAVEGADOR AL TERMINAR TODAS LAS BÚSQUEDAS DE ESTE PORTAL
                logger.info(f"🔒 Cerrando navegador de {nombre_portal}...")
                scraper.cerrar_navegador()
                
    except Exception as e:
        logger.critical(f"💥 Falla general: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e), 'total_ofertas': total_ofertas_guardadas}
        
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 RESUMEN FINAL: {total_ofertas_guardadas} ofertas guardadas | ⏱️ Tiempo: {time.time() - start_time:.2f}s")
    logger.info(f"{'='*60}")
    
    return {'success': True, 'total_ofertas': total_ofertas_guardadas, 'resultados_por_scraper': resultados_por_scraper, 'tiempo_ejecucion': time.time() - start_time, 'payloads': todos_los_payloads}

if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="INFO")
    
    limites_dinamicos = {
        "Computrabajo": 20,
        "Bumeran": 20,
        "LinkedIn": 15  # Reducido para ahorrar tiempo
    }
    
    resultados = ejecutar_pipeline(
        limites_por_portal=limites_dinamicos,
        usar_bumeran=True, 
        usar_computrabajo=True, 
        usar_linkedin=True,
        usar_indeed=False, 
        usar_nlp=True
    )
    
    if resultados['success']: print(f"\n✅ Pipeline completado: {resultados['total_ofertas']} ofertas guardadas")
    else: print(f"\n❌ Error: {resultados.get('error')}")
