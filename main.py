"""
Módulo: main.py (Optimizado y Unificado)
Ejecuta el pipeline completo usando los scrapers refactorizados.
"""
import sys
import os
import time
import hashlib
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from nlp.text_cleaner import TextCleaner
from nlp.ai_extractor import AIExtractor
from storage.sheets_handler import SheetsHandler, SheetsHandlerSimulado
from scrapers.computrabajo_scraper import ComputrabajoScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.bumeran_scraper import BumeranScraper
from scrapers.indeed_scraper import IndeedScraperPlaywright

def es_titulo_relevante(titulo: str, puesto_buscado: str) -> bool:
    titulo_lower = titulo.lower().strip()
    puesto_lower = puesto_buscado.lower().strip()
    if puesto_lower in titulo_lower: 
        return True
    return any(gen in titulo_lower for gen in ["practicante", "pasante", "trainee", "intern", "prácticas", "estudiante", "apoyo"])

def validar_contenido_semantico(oferta: dict, puesto: str) -> bool:
    DICCIONARIO_AREAS = {
        "marketing": ["marketing", "branding", "digital", "seo", "sem", "growth", "comunicaciones", "publicidad", "social media"],
        "datos": ["data", "datos", "analytics", "analista de datos", "bi", "business intelligence", "sql", "power bi", "python", "excel", "dashboard"]
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
        
    return any(p in titulo for p in palabras_clave) or any(p in texto for p in palabras_clave)

def procesar_oferta_con_nlp(oferta: dict, nombre_plataforma: str, lugar: str, cleaner: TextCleaner, extractor: AIExtractor) -> Optional[Dict]:
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
        
        reqs_raw = datos_extraidos.get("requisitos", [])
        reqs_text = [r.get("texto", "") for r in reqs_raw if r.get("texto")]
        requisitos_comprimidos = "; ".join(reqs_text[:8])
        
        bens_raw = datos_extraidos.get("beneficios", "")
        bens_list = [b.strip("• \n\r") for b in bens_raw.split("\n") if b.strip() and len(b.strip()) > 5]
        beneficios_comprimidos = "; ".join(bens_list[:5])
        
        empresa_nlp = datos_extraidos.get("empresa", "No especificada")
        empresa_scraper = oferta.get("empresa_extraida", "")
        
        if empresa_nlp in ["No especificada", titulo_oferta, ""] and empresa_scraper and len(empresa_scraper) > 3:
            empresa_final = empresa_scraper
        else:
            empresa_final = empresa_nlp
        
        return {
            "id_oferta": f"{nombre_plataforma[:3].upper()}-{id_unico}",
            "fecha_scraping": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "plataforma_origen": nombre_plataforma,
            "link_oferta": oferta.get("link_oferta", ""),
            "titulo_puesto": titulo_oferta if titulo_oferta else datos_extraidos.get("titulo_puesto", "No especificado"),
            "empresa": empresa_final,
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

def ejecutar_pipeline(limites_por_portal: dict = None, usar_bumeran: bool = True, usar_computrabajo: bool = True, usar_linkedin: bool = True, usar_indeed: bool = True, usar_nlp: bool = True) -> Dict:
    logger.info("=" * 60 + "\n🏁 INICIANDO PIPELINE DE AUTOMATIZACIÓN - LABORAL AI\n" + "=" * 60)
    start_time = time.time()
    cleaner, extractor = TextCleaner(), AIExtractor()
    
    try: 
        storage = SheetsHandler()
    except Exception: 
        storage = SheetsHandlerSimulado()
    
    busquedas_a_ejecutar = storage.obtener_busquedas_activas()
    if not busquedas_a_ejecutar:
        return {'success': False, 'error': 'No hay búsquedas activas en Config_Busquedas', 'total_ofertas': 0}
    
    logger.info(f"🎯 Se ejecutarán {len(busquedas_a_ejecutar)} búsqueda(s):")
    for i, b in enumerate(busquedas_a_ejecutar, 1):
        logger.info(f"   {i}. {b['puesto']} en {b['lugar']}")
    
    if limites_por_portal is None:
        limites_por_portal = {"Computrabajo": 20, "Bumeran": 20, "LinkedIn": 20, "Indeed": 20}
    
    total_ofertas_guardadas = 0
    resultados_por_scraper = {}
    
    portales = []
    if usar_computrabajo: portales.append({'scraper': ComputrabajoScraper(), 'nombre': 'Computrabajo'})
    if usar_bumeran: portales.append({'scraper': BumeranScraper(), 'nombre': 'Bumeran'})
    if usar_linkedin: portales.append({'scraper': LinkedInScraper(), 'nombre': 'LinkedIn'})
    if usar_indeed: portales.append({'scraper': IndeedScraperPlaywright(), 'nombre': 'Indeed'})
    
    if not portales:
        return {'success': False, 'error': 'No hay portales activados', 'total_ofertas': 0}

    try:
        for portal in portales:
            scraper = portal['scraper']
            nombre_portal = portal['nombre']
            limite_portal = limites_por_portal.get(nombre_portal, 20)
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🌐 INICIANDO NAVEGADOR PARA: {nombre_portal}")
            logger.info(f"{'='*60}")
            
            # 1. Detectamos si el scraper es asíncrono (como Indeed)
            es_asincrono = asyncio.iscoroutinefunction(scraper.iniciar_navegador)
            loop = None
            
            # 2. Iniciamos el navegador según su tipo
            if es_asincrono:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(scraper.iniciar_navegador(headless=True))
            else:
                scraper.iniciar_navegador(headless=True)
            
            try:
                for busqueda in busquedas_a_ejecutar:
                    puesto = busqueda['puesto']
                    lugar = busqueda['lugar']
                    
                    logger.info(f"\n🔍 Buscando: '{puesto}' en '{lugar}' (Límite: {limite_portal})")
                    
                    try:
                        # 💡 CAMBIO AQUÍ: Pedimos el doble al scraper (limite_extraccion)
                        limite_extraccion = limite_portal * 2 
                        
                        # 3. Recolectamos ofertas según su tipo
                        if es_asincrono:
                            ofertas_crudas = loop.run_until_complete(scraper.recolectar_ofertas(
                                limite_ofertas=limite_extraccion, 
                                puesto=puesto, 
                                lugar=lugar, 
                                filtro_relevancia_cb=es_titulo_relevante
                            ))
                        else:
                            ofertas_crudas = scraper.recolectar_ofertas(
                                limite_ofertas=limite_extraccion, 
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
                    
                    # 💡 CAMBIO AQUÍ: Filtramos y luego cortamos a la cantidad original
                    ofertas_validadas = [ofr for ofr in ofertas_crudas if validar_contenido_semantico(ofr, puesto)]
                    ofertas_validadas = ofertas_validadas[:limite_portal] # Recorta exactamente a 20 (o el límite que sea)
                    
                    logger.info(f"✅ Ofertas purificadas: {len(ofertas_validadas)} (recortado al límite de {limite_portal})")
                    
                    payloads = []
                    for oferta in ofertas_validadas:
                        oferta['puesto_buscado'] = puesto
                        if usar_nlp:
                            payload = procesar_oferta_con_nlp(oferta, nombre_portal, lugar, cleaner, extractor)
                            if payload: 
                                payloads.append(payload)
                    
                    stats = storage.verificar_y_guardar(ofertas_del_scraper=payloads, nombre_scraper=nombre_portal, puesto=puesto, lugar=lugar)
                    
                    key_res = f"{nombre_portal}_{puesto.replace(' ', '_')}_{lugar}"
                    resultados_por_scraper[key_res] = {'extraidas': len(ofertas_validadas), 'guardadas': stats.get('guardadas', 0)}
                    total_ofertas_guardadas += stats.get('guardadas', 0)
                    
            finally:
                logger.info(f"🔒 Cerrando navegador de {nombre_portal}...")
                # 4. Cerramos el navegador según su tipo
                if es_asincrono:
                    loop.run_until_complete(scraper.cerrar_navegador())
                    loop.close()
                else:
                    scraper.cerrar_navegador()
                
    except Exception as e:
        logger.critical(f"💥 Falla general: {e}")
        return {'success': False, 'error': str(e), 'total_ofertas': total_ofertas_guardadas}
        
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 RESUMEN FINAL: {total_ofertas_guardadas} ofertas guardadas | ⏱️ Tiempo: {time.time() - start_time:.2f}s")
    logger.info(f"{'='*60}")
    
    return {'success': True, 'total_ofertas': total_ofertas_guardadas}

if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="INFO")
    
    limites_dinamicos = {
        "Computrabajo": 150,
        "Bumeran": 150,
        "LinkedIn": 150,
        "Indeed": 20
    }
    
    resultados = ejecutar_pipeline(
        limites_por_portal=limites_dinamicos,
        usar_bumeran=True, 
        usar_computrabajo=True, 
        usar_linkedin=True,
        usar_indeed=False, 
        usar_nlp=True
    )
    
    if resultados['success']: 
        print(f"\n✅ Pipeline completado: {resultados['total_ofertas']} ofertas guardadas")
    else: 
        print(f"\n❌ Error: {resultados.get('error')}")
