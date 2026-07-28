"""
Módulo: storage/sheets_handler.py
Propósito: Persistencia de ofertas en Google Sheets con verificación post-scraper.
Compatible con Hugging Face Spaces (usa variables de entorno).
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

# ============================================================
# CONFIGURACIÓN: Soporta tanto local como Hugging Face
# ============================================================

def obtener_credenciales():
    """
    Obtiene las credenciales de Google desde:
    1. Variable de entorno GOOGLE_CREDENTIALS_JSON (Hugging Face)
    2. Archivo local config/credentials.json (desarrollo local)
    """
    # Intentar primero desde variable de entorno (Hugging Face)
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    
    if creds_json:
        logger.info(" Usando credenciales desde variable de entorno (Hugging Face)")
        try:
            creds_dict = json.loads(creds_json)
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            return Credentials.from_service_account_info(creds_dict, scopes=scopes)
        except Exception as e:
            logger.error(f"❌ Error parseando GOOGLE_CREDENTIALS_JSON: {e}")
            return None
    
    # Fallback: archivo local (solo para desarrollo)
    creds_file = os.path.join("config", "credentials.json")
    if os.path.exists(creds_file):
        logger.info(f"🔑 Usando credenciales desde archivo local: {creds_file}")
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            return Credentials.from_service_account_file(creds_file, scopes=scopes)
        except Exception as e:
            logger.error(f"❌ Error cargando {creds_file}: {e}")
            return None
    
    logger.warning("⚠️ No se encontraron credenciales de Google. Modo simulación activado.")
    return None


class SheetsHandler:
    """
    Gestor de persistencia en Google Sheets con verificación post-scraper.
    """
    
    def __init__(self, sheet_name: str = "Laboral_AI_Scraper_Data"):
        self.sheet_name = sheet_name
        self.client = None
        self.sheet = None
        self._conectar_google_api()
    
    def _conectar_google_api(self):
        """Se conecta a Google Drive usando credenciales desde entorno o archivo."""
        creds = obtener_credenciales()
        if not creds:
            logger.warning("⚠️ Modo simulación: los datos NO se guardarán en Google Sheets")
            return
        
        try:
            logger.info(" Conectando con Google Sheets API...")
            self.client = gspread.authorize(creds)
            
            try:
                self.sheet = self.client.open(self.sheet_name)
                logger.info(f"✅ Conectado a: '{self.sheet_name}'")
            except gspread.SpreadsheetNotFound:
                logger.info(f"📄 Creando nuevo spreadsheet: '{self.sheet_name}'")
                self.sheet = self.client.create(self.sheet_name)
                self._inicializar_estructura_hojas()
                logger.success("✅ Spreadsheet creado e inicializado")
                
        except Exception as e:
            logger.error(f"❌ Error conectando con Google Sheets: {e}")
            self.client = None
            self.sheet = None
    
    def _inicializar_estructura_hojas(self):
        """Crea las pestañas necesarias con la estructura correcta de 15 columnas."""
        if not self.sheet:
            return
        
        try:
            # Pestaña 1: Configuración de búsquedas
            try:
                worksheet_config = self.sheet.get_worksheet(0)
                worksheet_config.update_title("Config_Busquedas")
            except Exception:
                worksheet_config = self.sheet.add_worksheet(
                    title="Config_Busquedas", rows="100", cols="5"
                )
            
            # Limpiar y poner headers
            worksheet_config.clear()
            worksheet_config.append_row([
                "Puesto", "Lugar", "Activo", "Ultima_Ejecucion", "Total_Ofertas"
            ])
            worksheet_config.append_row([
                "practicante de datos", "lima", "SI", "-", "0"
            ])
            
            # Pestaña 2: Ofertas extraídas (15 columnas CORRECTAS)
            try:
                worksheet_ofertas = self.sheet.worksheet("Ofertas_Extraidas")
            except gspread.WorksheetNotFound:
                worksheet_ofertas = self.sheet.add_worksheet(
                    title="Ofertas_Extraidas", rows="5000", cols="15"
                )
            
            worksheet_ofertas.clear()
            worksheet_ofertas.append_row([
                "id_oferta",           # 1
                "fecha_scraping",      # 2
                "plataforma_origen",   # 3
                "link_oferta",         # 4
                "titulo_puesto",       # 5
                "empresa",             # 6
                "modalidad",           # 7
                "disponible_hasta",    # 8
                "nivel",               # 9
                "horario",             # 10
                "departamento",        # 11
                "area_categoria",      # 12
                "descripcion_breve",   # 13
                "requisitos",          # 14
                "beneficios"           # 15
            ])
            
            logger.info("📊 Estructura de hojas inicializada correctamente")
            
        except Exception as e:
            logger.error(f" Error inicializando estructura: {e}")
    
    def obtener_busquedas_activas(self) -> List[Dict]:
        """Lee 'Config_Busquedas' y devuelve lista de búsquedas activas."""
        if not self.sheet:
            logger.warning("⚠️ Sin conexión a Sheets. Retornando búsqueda por defecto.")
            return [{"puesto": "practicante de datos", "lugar": "lima"}]
        
        try:
            try:
                worksheet = self.sheet.worksheet("Config_Busquedas")
            except gspread.WorksheetNotFound:
                self._inicializar_estructura_hojas()
                worksheet = self.sheet.worksheet("Config_Busquedas")
            
            registros = worksheet.get_all_records()
            busquedas_activas = []
            
            for reg in registros:
                puesto = str(reg.get("Puesto", "")).strip()
                lugar = str(reg.get("Lugar", "lima")).strip().lower().replace(" ", "-")
                activo = str(reg.get("Activo", "")).strip().upper()
                
                if puesto and activo == "SI":
                    busquedas_activas.append({
                        "puesto": puesto,
                        "lugar": lugar if lugar else "lima"
                    })
            
            logger.info(f" {len(busquedas_activas)} búsquedas activas encontradas")
            return busquedas_activas if busquedas_activas else [
                {"puesto": "practicante de datos", "lugar": "lima"}
            ]
            
        except Exception as e:
            logger.error(f"❌ Error leyendo configuración: {e}")
            return [{"puesto": "practicante de datos", "lugar": "lima"}]
    
    # ============================================================
    # 🎯 MÉTODO CLAVE: Verificación Post-Scraper
    # ============================================================
    
    def verificar_y_guardar(
        self, 
        ofertas_del_scraper: List[Dict], 
        nombre_scraper: str,
        puesto: str,
        lugar: str
    ) -> Dict:
        """
        Verifica, limpia y guarda las ofertas de UN scraper específico.
        Retorna estadísticas detalladas para el dashboard de Streamlit.
        
        Args:
            ofertas_del_scraper: Lista de dicts con las ofertas extraídas
            nombre_scraper: Nombre del scraper (ej: "Bumeran", "Computrabajo")
            puesto: Puesto buscado
            lugar: Ubicación buscada
            
        Returns:
            Dict con estadísticas: {
                'total_recibidas': int,
                'validas': int,
                'duplicadas': int,
                'guardadas': int,
                'errores': int,
                'ids_guardados': list
            }
        """
        stats = {
            'total_recibidas': len(ofertas_del_scraper),
            'validas': 0,
            'duplicadas': 0,
            'guardadas': 0,
            'errores': 0,
            'ids_guardados': [],
            'scraper': nombre_scraper,
            'puesto': puesto,
            'lugar': lugar
        }
        
        if not ofertas_del_scraper:
            logger.warning(f"⚠️ {nombre_scraper}: 0 ofertas recibidas")
            return stats
        
        if not self.sheet:
            logger.error(f"❌ {nombre_scraper}: No hay conexión a Sheets. Modo simulación.")
            stats['errores'] = stats['total_recibidas']
            return stats
        
        try:
            hoja = self.sheet.worksheet("Ofertas_Extraidas")
            
            # Obtener IDs existentes para anti-duplicados
            try:
                ids_existentes = set(hoja.col_values(1))
            except Exception:
                ids_existentes = set()
            
            filas_a_insertar = []
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for oferta in ofertas_del_scraper:
                # Validar que tenga datos mínimos
                if not oferta.get('link_oferta') or not oferta.get('titulo_puesto'):
                    stats['errores'] += 1
                    continue
                
                # Generar ID único si no existe
                id_oferta = oferta.get('id_oferta')
                if not id_oferta:
                    # Crear ID basado en plataforma + link (hash simple)
                    id_oferta = f"{nombre_scraper}_{oferta['link_oferta'][-20:]}"
                    oferta['id_oferta'] = id_oferta
                
                # Verificar duplicados
                if id_oferta in ids_existentes:
                    stats['duplicadas'] += 1
                    continue
                
                stats['validas'] += 1
                
                # Construir fila con TODAS las 15 columnas
                fila = [
                    id_oferta,                                              # 1
                    fecha_actual,                                           # 2
                    nombre_scraper,                                         # 3
                    oferta.get('link_oferta', ''),                          # 4
                    oferta.get('titulo_puesto', ''),                        # 5
                    oferta.get('empresa', 'Confidencial'),                  # 6
                    oferta.get('modalidad', 'No especificado'),             # 7
                    oferta.get('disponible_hasta', ''),                     # 8
                    oferta.get('nivel', 'No especificado'),                 # 9
                    oferta.get('horario', 'Tiempo Completo'),               # 10
                    oferta.get('departamento', lugar.capitalize()),         # 11
                    oferta.get('area_categoria', ''),                       # 12
                    oferta.get('descripcion_breve', '')[:3000],             # 13 (max 3000 chars)
                    oferta.get('requisitos', ''),                           # 14
                    oferta.get('beneficios', '')                            # 15
                ]
                
                filas_a_insertar.append(fila)
                ids_existentes.add(id_oferta)  # Prevenir duplicados en el mismo batch
            
            # Guardar en Sheets
            if filas_a_insertar:
                hoja.append_rows(filas_a_insertar, value_input_option="RAW")
                stats['guardadas'] = len(filas_a_insertar)
                stats['ids_guardados'] = [f[0] for f in filas_a_insertar]
                logger.success(
                    f"✅ {nombre_scraper}: {stats['guardadas']} ofertas guardadas "
                    f"({stats['duplicadas']} duplicadas, {stats['errores']} errores)"
                )
            else:
                logger.info(f"️ {nombre_scraper}: Todas las ofertas ya existían")
            
            # Actualizar contador en Config_Busquedas
            self._actualizar_contador(puesto, lugar, stats['guardadas'])
            
        except gspread.WorksheetNotFound:
            logger.error(f"❌ No existe la pestaña 'Ofertas_Extraidas'. Re-inicializando...")
            self._inicializar_estructura_hojas()
            return self.verificar_y_guardar(ofertas_del_scraper, nombre_scraper, puesto, lugar)
        except Exception as e:
            logger.error(f"❌ Error en verificar_y_guardar ({nombre_scraper}): {e}")
            stats['errores'] = stats['total_recibidas'] - stats['validas']
        
        return stats
    
    def _actualizar_contador(self, puesto: str, lugar: str, nuevas_ofertas: int):
        """Actualiza el contador de ofertas en Config_Busquedas."""
        if not self.sheet:
            return
        
        try:
            worksheet = self.sheet.worksheet("Config_Busquedas")
            registros = worksheet.get_all_values()
            
            for i, row in enumerate(registros):
                if i > 0 and len(row) >= 5:
                    if row[0].lower() == puesto.lower() and row[1].lower() == lugar.lower():
                        # Sumar al contador existente
                        try:
                            actual = int(row[4]) if row[4] else 0
                        except ValueError:
                            actual = 0
                        worksheet.update_cell(i + 1, 4, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        worksheet.update_cell(i + 1, 5, str(actual + nuevas_ofertas))
                        break
        except Exception as e:
            logger.debug(f"️ No se pudo actualizar contador: {e}")
    
    def obtener_estadisticas(self) -> Dict:
        """Retorna estadísticas generales del spreadsheet."""
        if not self.sheet:
            return {'error': 'Sin conexión a Sheets'}
        
        try:
            hoja = self.sheet.worksheet("Ofertas_Extraidas")
            total_filas = len(hoja.get_all_values()) - 1  # Restar header
            
            # Contar por plataforma
            plataformas = hoja.col_values(3)[1:]  # Saltar header
            conteo_plataformas = {}
            for p in plataformas:
                if p:
                    conteo_plataformas[p] = conteo_plataformas.get(p, 0) + 1
            
            return {
                'total_ofertas': total_filas,
                'por_plataforma': conteo_plataformas,
                'ultima_actualizacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            return {'error': str(e)}
    
    def cerrar(self):
        """Cierra la conexión (opcional, gspread la maneja solo)."""
        self.client = None
        self.sheet = None
        logger.info(" Conexión a Google Sheets cerrada")


# ============================================================
# MODO SIMULACIÓN (para testing sin credenciales)
# ============================================================

class SheetsHandlerSimulado(SheetsHandler):
    """Versión simulada para desarrollo sin credenciales de Google."""
    
    def __init__(self, sheet_name: str = "Laboral_AI_Scraper_Data"):
        self.sheet_name = sheet_name
        self.client = None
        self.sheet = None
        self.ofertas_guardadas = []
        logger.info("🧪 SheetsHandlerSimulado inicializado (sin conexión real)")
    
    def verificar_y_guardar(self, ofertas_del_scraper, nombre_scraper, puesto, lugar):
        stats = {
            'total_recibidas': len(ofertas_del_scraper),
            'validas': len(ofertas_del_scraper),
            'duplicadas': 0,
            'guardadas': len(ofertas_del_scraper),
            'errores': 0,
            'ids_guardados': [f"sim_{i}" for i in range(len(ofertas_del_scraper))],
            'scraper': nombre_scraper,
            'puesto': puesto,
            'lugar': lugar,
            'modo_simulacion': True
        }
        self.ofertas_guardadas.extend(ofertas_del_scraper)
        logger.info(f" [SIMULADO] {nombre_scraper}: {stats['guardadas']} ofertas 'guardadas'")
        return stats
    
    def obtener_estadisticas(self):
        return {
            'total_ofertas': len(self.ofertas_guardadas),
            'modo_simulacion': True
        }