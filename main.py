"""
Módulo: main.py
Orquestador unificado. Soporta sync/async sin fugas de loop.
"""
import time
import hashlib
import asyncio
from datetime import datetime
from typing import Dict, Optional, List
from loguru import logger

from config.settings import DEST_COLUMNS, GOOGLE_SHEET_NAME
from nlp.text_cleaner import TextCleaner
from nlp.ai_extractor import AIExtractor
from storage.sheets_handler import SheetsHandler, SheetsHandlerSimulado
from scrapers.computrabajo_scraper import ComputrabajoScraper
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.bumeran_scraper import BumeranScraper
from scrapers.indeed_scraper import IndeedScraperPlaywright

AREAS_SEMANTICAS = {
    "marketing": ["marketing", "branding", "digital", "seo", "sem", "growth",
                  "comunicaciones", "publicidad", "social media", "community manager"],
    "datos": ["data", "datos", "analytics", "analista de datos", "bi",
              "business intelligence", "sql", "power bi", "python", "excel",
              "dashboard", "data analyst", "cientifico de datos"],
    "desarrollo": ["software", "developer", "desarrollador", "programador",
                   "backend", "frontend", "fullstack", "web", "aplicaciones"],
    "contabilidad": ["contable", "contabilidad", "finanzas", "tesoreria", "facturacion"]
}

DEFAULT_LIMITE_PORTAL = 20


def es_titulo_relevante(titulo: str, puesto_buscado: str) -> bool:
    t = titulo.lower().strip()
    p = puesto_buscado.lower().strip()
    if p in t:
        return True
    genericos = ["practicante", "pasante", "trainee", "intern", "prácticas", "estudiante", "apoyo"]
    return any(g in t for g in genericos)


def validar_contenido_semantico(oferta: dict, puesto: str) -> bool:
    texto = oferta.get("texto_crudo", "").lower()
    titulo = oferta.get("titulo_puesto", "").lower()
    puesto_norm = puesto.lower()

    palabras_clave = [puesto_norm]
    for area, keywords in AREAS_SEMANTICAS.items():
        if area in puesto_norm:
            palabras_clave.extend(keywords)
            break
    else:
        palabras_clave.extend(puesto_norm.split())

    return any(p in titulo for p in palabras_clave) or any(p in texto for p in palabras_clave)


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

        id_unico = hashlib.md5(
            f"{nombre_plataforma}_{oferta.get('link_oferta', '')}".encode()
        ).hexdigest()[:12]

        puesto_norm = oferta.get("puesto_buscado", "").lower()
        categoria = "Marketing" if "marketing" in puesto_norm else "Data & Analytics"

        reqs_raw = datos_extraidos.get("requisitos", [])
        reqs_text = [r.get("texto", "") for r in reqs_raw if r.get("texto")]
        requisitos_comp = "; ".join(reqs_text[:8])

        bens_raw = datos_extraidos.get("beneficios", "")
        bens_list = [b.strip("• \n\r") for b in bens_raw.split("\n") if b.strip() and len(b.strip()) > 5]
        beneficios_comp = "; ".join(bens_list[:5])

        empresa_nlp = datos_extraidos.get("empresa", "No especificada")
        empresa_scraper = oferta.get("empresa_extraida", "")

        if empresa_nlp in ["No especificada", titulo_oferta, ""] and empresa_scraper and len(empresa_scraper) > 3:
            empresa_final = empresa_scraper
        else:
            empresa_final = empresa_nlp

        payload = {
            "id_oferta": f"{nombre_plataforma[:3].upper()}-{id_unico}",
            "fecha_scraping": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "plataforma_origen": nombre_plataforma,
            "link_oferta": oferta.get("link_oferta", ""),
            "titulo_puesto": titulo_oferta or datos_extraidos.get("titulo_puesto", "No especificado"),
            "empresa": empresa_final,
            "modalidad": datos_extraidos.get("modalidad", "Presencial"),
            "disponible_hasta": "-",
            "horario": datos_extraidos.get("horario", "Tiempo Completo"),
            "departamento": lugar.capitalize(),
            "area_categoria": categoria,
            "descripcion_breve": texto_limpio[:2000],
            "requisitos": requisitos_comp or "No especificados",
            "beneficios": beneficios_comp or "No especificados"
        }

        # Validación estricta: solo retornar si tiene todas las columnas esperadas
        if all(k in payload for k in DEST_COLUMNS):
            return payload
        else:
            faltantes = [k for k in DEST_COLUMNS if k not in payload]
            logger.warning(f"Payload incompleto, faltan: {faltantes}")
            return None

    except Exception as e:
        logger.error(f"❌ Error NLP: {e}")
        return None


def ejecutar_pipeline(
    limites_por_portal: Optional[dict] = None,
    usar_bumeran: bool = True,
    usar_computrabajo: bool = True,
    usar_linkedin: bool = True,
    usar_indeed: bool = True,
    usar_nlp: bool = True
) -> Dict:
    logger.info("=" * 60)
    logger.info("🏁 INICIANDO PIPELINE - LABORAL AI")
    logger.info("=" * 60)

    inicio = time.time()
    cleaner = TextCleaner()
    extractor = AIExtractor()

    try:
        storage = SheetsHandler()
    except Exception:
        storage = SheetsHandlerSimulado()

    busquedas = storage.obtener_busquedas_activas()
    if not busquedas:
        return {'success': False, 'error': 'No hay búsquedas activas', 'total_ofertas': 0}

    logger.info(f"🎯 {len(busquedas)} búsqueda(s) activas:")
    for i, b in enumerate(busquedas, 1):
        logger.info(f"   {i}. {b['puesto']} en {b['lugar']}")

    if limites_por_portal is None:
        limites_por_portal = {
            "Computrabajo": DEFAULT_LIMITE_PORTAL,
            "Bumeran": DEFAULT_LIMITE_PORTAL,
            "LinkedIn": DEFAULT_LIMITE_PORTAL,
            "Indeed": DEFAULT_LIMITE_PORTAL
        }

    total_guardadas = 0
    resultados = {}

    portales = []
    if usar_computrabajo:
        portales.append({'scraper': ComputrabajoScraper(), 'nombre': 'Computrabajo'})
    if usar_bumeran:
        portales.append({'scraper': BumeranScraper(), 'nombre': 'Bumeran'})
    if usar_linkedin:
        portales.append({'scraper': LinkedInScraper(), 'nombre': 'LinkedIn'})
    if usar_indeed:
        portales.append({'scraper': IndeedScraperPlaywright(), 'nombre': 'Indeed'})

    if not portales:
        return {'success': False, 'error': 'No hay portales activados', 'total_ofertas': 0}

    # Loop async compartido para todos los scrapers async
    loop_async = None
    hay_async = any(
        asyncio.iscoroutinefunction(p['scraper'].iniciar_navegador)
        for p in portales
    )
    if hay_async:
        try:
            loop_async = asyncio.get_running_loop()
        except RuntimeError:
            loop_async = asyncio.new_event_loop()
            asyncio.set_event_loop(loop_async)

    try:
        for portal in portales:
            scraper = portal['scraper']
            nombre = portal['nombre']
            limite = limites_por_portal.get(nombre, DEFAULT_LIMITE_PORTAL)
            es_async = asyncio.iscoroutinefunction(scraper.iniciar_navegador)

            logger.info(f"\n{'='*60}")
            logger.info(f"🌐 PORTAL: {nombre}")
            logger.info(f"{'='*60}")

            if es_async:
                loop_async.run_until_complete(scraper.iniciar_navegador(headless=True))
            else:
                scraper.iniciar_navegador(headless=True)

            try:
                for busqueda in busquedas:
                    puesto = busqueda['puesto']
                    lugar = busqueda['lugar']

                    logger.info(f"\n🔍 Buscando: '{puesto}' en '{lugar}' (Límite: {limite})")

                    try:
                        limite_extraccion = limite * 2

                        if es_async:
                            ofertas_crudas = loop_async.run_until_complete(
                                scraper.recolectar_ofertas(
                                    limite_ofertas=limite_extraccion,
                                    puesto=puesto,
                                    lugar=lugar,
                                    filtro_relevancia_cb=es_titulo_relevante
                                )
                            )
                        else:
                            ofertas_crudas = scraper.recolectar_ofertas(
                                limite_ofertas=limite_extraccion,
                                puesto=puesto,
                                lugar=lugar,
                                filtro_relevancia_cb=es_titulo_relevante
                            )
                    except Exception as e:
                        logger.error(f"❌ Fallo en {nombre} para '{puesto}': {e}")
                        continue

                    if not ofertas_crudas:
                        logger.warning(f"⚠️ 0 ofertas extraídas de {nombre} para '{puesto}'")
                        continue

                    ofertas_validadas = [o for o in ofertas_crudas if validar_contenido_semantico(o, puesto)]
                    ofertas_validadas = ofertas_validadas[:limite]

                    logger.info(f"✅ Purificadas: {len(ofertas_validadas)} (límite: {limite})")

                    payloads = []
                    for oferta in ofertas_validadas:
                        oferta['puesto_buscado'] = puesto
                        if usar_nlp:
                            payload = procesar_oferta_con_nlp(oferta, nombre, lugar, cleaner, extractor)
                            if payload:
                                payloads.append(payload)

                    stats = storage.verificar_y_guardar(
                        ofertas_del_scraper=payloads,
                        nombre_scraper=nombre,
                        puesto=puesto,
                        lugar=lugar
                    )

                    key = f"{nombre}_{puesto.replace(' ', '_')}_{lugar}"
                    resultados[key] = {
                        'extraidas': len(ofertas_validadas),
                        'guardadas': stats.get('guardadas', 0)
                    }
                    total_guardadas += stats.get('guardadas', 0)

            finally:
                logger.info(f"🔒 Cerrando navegador de {nombre}...")
                if es_async:
                    loop_async.run_until_complete(scraper.cerrar_navegador())
                else:
                    scraper.cerrar_navegador()

    except Exception as e:
        logger.critical(f"💥 Falla general: {e}")
        return {'success': False, 'error': str(e), 'total_ofertas': total_guardadas}

    finally:
        if loop_async and not loop_async.is_closed():
            loop_async.close()

    logger.info(f"\n{'='*60}")
    logger.info(f"📊 RESUMEN: {total_guardadas} guardadas | ⏱️ {time.time() - inicio:.2f}s")
    logger.info(f"{'='*60}")

    return {'success': True, 'total_ofertas': total_guardadas}


if __name__ == "__main__":
    import sys
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="INFO")

    limites = {
        "Computrabajo": 150,
        "Bumeran": 150,
        "LinkedIn": 150,
        "Indeed": 20
    }

    resultados = ejecutar_pipeline(
        limites_por_portal=limites,
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
