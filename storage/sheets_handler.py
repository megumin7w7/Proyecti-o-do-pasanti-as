"""
Módulo: storage/sheets_handler.py
Maneja la conexión a Google Sheets y provee un fallback simulado si no hay credenciales.
"""
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from loguru import logger
from config.settings import GOOGLE_SHEET_NAME, CREDENTIALS_FILE


class SheetsHandlerSimulado:
    """Clase de respaldo cuando no existen credenciales de Google Sheets."""
    def __init__(self):
        logger.warning("⚠️ Modo Simulación de Sheets activo (Sin conexión real).")

    def obtener_busquedas_activas(self) -> list:
        logger.info("📋 [Simulación] Usando búsqueda por defecto.")
        return [{"puesto": "practicante de datos", "lugar": "lima"}]

    def verificar_y_guardar(self, ofertas_del_scraper: list, nombre_scraper: str, puesto: str, lugar: str) -> dict:
        total = len(ofertas_del_scraper) if ofertas_del_scraper else 0
        logger.info(f"📊 [Simulación] {total} ofertas procesadas localmente (No enviadas a Sheets).")
        return {'guardadas': 0, 'duplicadas': 0, 'errores': 0}

    def actualizar_estado(self, puesto: str, lugar: str):
        pass


class SheetsHandler:
    """Manejador principal de Google Sheets con soporte para secrets de GitHub."""
    def __init__(self):
        self.client = None
        self.sheet = None
        self._conectar_google_api()

    def _conectar_google_api(self):
        """Se conecta usando Variable de Entorno (GitHub Actions) o archivo local."""
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        # 1. Intentar desde Variable de Entorno (GitHub Actions)
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            try:
                logger.info("🔑 Conectando con Google Sheets (desde Variable de Entorno)...")
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                self.client = gspread.authorize(creds)
                self._abrir_o_crear_sheet()
                return
            except Exception as e:
                logger.error(f"❌ Error al autenticar con GOOGLE_CREDENTIALS_JSON: {e}")

        # 2. Intentar desde archivo local (Desarrollo en PC)
        if os.path.exists(CREDENTIALS_FILE):
            try:
                logger.info(f"🔑 Conectando con Google Sheets (desde {CREDENTIALS_FILE})...")
                creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
                self.client = gspread.authorize(creds)
                self._abrir_o_crear_sheet()
                return
            except Exception as e:
                logger.error(f"❌ Error al abrir archivo de credenciales local: {e}")

        # 3. Si no hay nada configurado
        logger.warning("⚠️ No se encontraron credenciales válidas.")

    def _abrir_o_crear_sheet(self):
        try:
            self.sheet = self.client.open(GOOGLE_SHEET_NAME)
            logger.info(f"✅ Conectado exitosamente a Google Sheet: '{GOOGLE_SHEET_NAME}'")
        except gspread.SpreadsheetNotFound:
            try:
                logger.info(f"📄 No existe '{GOOGLE_SHEET_NAME}'. Creando uno nuevo...")
                self.sheet = self.client.create(GOOGLE_SHEET_NAME)
                self._inicializar_estructura_hojas()
            except Exception as e:
                logger.error(f"❌ No se pudo crear la hoja. Revisa los permisos de la API: {e}")
        except Exception as e:
            logger.error(f"❌ Error al acceder a '{GOOGLE_SHEET_NAME}': {e}. ¿Compartiste la hoja con el correo de la Service Account?")

    def _inicializar_estructura_hojas(self):
        if not self.sheet:
            return
        try:
            worksheet_config = self.sheet.get_worksheet(0)
            worksheet_config.update_title("Config_Busquedas")
            worksheet_config.clear()
            worksheet_config.append_row(["Puesto", "Lugar", "Activo", "Ultima_Ejecucion"])
            worksheet_config.append_row(["practicante de datos", "lima", "SI", "-"])
            
            try:
                worksheet_ofertas = self.sheet.worksheet("Ofertas_Extraidas")
            except gspread.WorksheetNotFound:
                worksheet_ofertas = self.sheet.add_worksheet(title="Ofertas_Extraidas", rows="1000", cols="14")
            
            worksheet_ofertas.clear()
            worksheet_ofertas.append_row([
                "id_oferta", "fecha_scraping", "plataforma_origen", "link_oferta", 
                "titulo_puesto", "empresa", "modalidad", "disponible_hasta", 
                "horario", "departamento", "area_categoria", 
                "descripcion_breve", "requisitos", "beneficios"
            ])
            logger.info("📊 Estructura de pestañas inicializada correctamente.")
        except Exception as e:
            logger.error(f"❌ Error al estructurar pestañas: {e}")

    def obtener_busquedas_activas(self) -> list:
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
                    busquedas_activas.append({"puesto": puesto, "lugar": lugar if lugar else "lima"})
            
            return busquedas_activas if busquedas_activas else [{"puesto": "practicante de datos", "lugar": "lima"}]
        except Exception as e:
            logger.error(f"❌ Error leyendo configuración: {e}")
            return [{"puesto": "practicante de datos", "lugar": "lima"}]

    def verificar_y_guardar(self, ofertas_del_scraper: list, nombre_scraper: str, puesto: str, lugar: str) -> dict:
        if not ofertas_del_scraper:
            return {'guardadas': 0, 'duplicadas': 0, 'errores': 0}
        if not self.sheet:
            logger.error("❌ Sin conexión a Google Sheets")
            return {'guardadas': 0, 'duplicadas': 0, 'errores': len(ofertas_del_scraper)}
        
        filas_a_insertar, contador_nuevas, contador_duplicadas = [], 0, 0
        
        try:
            hoja_real = self.sheet.worksheet("Ofertas_Extraidas")
            valores_existentes = hoja_real.col_values(1)  
            
            for payload in ofertas_del_scraper:
                if payload["id_oferta"] in valores_existentes:
                    contador_duplicadas += 1
                    continue
                
                fila = [
                    payload.get("id_oferta"), payload.get("fecha_scraping"), payload.get("plataforma_origen"),
                    payload.get("link_oferta"), payload.get("titulo_puesto"), payload.get("empresa"),
                    payload.get("modalidad"), payload.get("disponible_hasta"), payload.get("horario"),
                    payload.get("departamento"), payload.get("area_categoria"), payload.get("descripcion_breve"),
                    payload.get("requisitos"), payload.get("beneficios")
                ]
                filas_a_insertar.append(fila)
                contador_nuevas += 1
            
            if filas_a_insertar:
                hoja_real.append_rows(filas_a_insertar, value_input_option="RAW")
                logger.info(f"💾 ¡Lote procesado! {contador_nuevas} filas nuevas insertadas en Google Sheets.")
            
            self.actualizar_estado(puesto, lugar)
            return {'guardadas': contador_nuevas, 'duplicadas': contador_duplicadas, 'errores': 0}
            
        except gspread.WorksheetNotFound:
            self._inicializar_estructura_hojas()
            return self.verificar_y_guardar(ofertas_del_scraper, nombre_scraper, puesto, lugar)
        except Exception as e:
            logger.error(f"❌ Error crítico guardando en Sheets: {e}")
            return {'guardadas': 0, 'duplicadas': 0, 'errores': len(ofertas_del_scraper)}

    def actualizar_estado(self, puesto: str, lugar: str):
        if not self.sheet:
            return
        try:
            worksheet = self.sheet.worksheet("Config_Busquedas")
            registros = worksheet.get_all_values()
            for i, row in enumerate(registros):
                if i > 0 and len(row) >= 2 and row[0].lower() == puesto.lower() and row[1].lower() == lugar.lower():
                    worksheet.update_cell(i+1, 4, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    break
        except Exception as e:
            logger.error(f"❌ Error actualizando estado: {e}")
