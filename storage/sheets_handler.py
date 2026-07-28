"""
Módulo: sheets_handler.py (Sin campo nivel, 14 columnas)
"""
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime
from loguru import logger
from config.settings import GOOGLE_SHEET_NAME, CREDENTIALS_FILE

class SheetsHandler:
    def __init__(self):
        self.client = None
        self.sheet = None
        self._conectar_google_api()

    def _conectar_google_api(self):
        if not os.path.exists(CREDENTIALS_FILE):
            logger.warning(f"⚠️ No se encontró el archivo '{CREDENTIALS_FILE}'")
            return
        try:
            logger.info("🔑 Conectando con API de Google Drive...")
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
            self.client = gspread.authorize(creds)
            try:
                self.sheet = self.client.open(GOOGLE_SHEET_NAME)
                logger.info(f"✅ Conectado a: '{GOOGLE_SHEET_NAME}'")
            except gspread.SpreadsheetNotFound:
                logger.info(f"📄 Creando nuevo archivo: '{GOOGLE_SHEET_NAME}'")
                self.sheet = self.client.create(GOOGLE_SHEET_NAME)
                self._inicializar_estructura_hojas()
        except Exception as e:
            logger.error(f"❌ Error conectando con Google Sheets: {e}")

    def _inicializar_estructura_hojas(self):
        if not self.sheet:
            return
        try:
            worksheet_config = self.sheet.get_worksheet(0)
            worksheet_config.update_title("Config_Busquedas")
            worksheet_config.append_row(["Puesto", "Lugar", "Activo", "Ultima_Ejecucion"])
            worksheet_config.append_row(["practicante de datos", "lima", "SI", "-"])
            
            # ✅ 14 COLUMNAS (sin "nivel")
            worksheet_ofertas = self.sheet.add_worksheet(title="Ofertas_Extraidas", rows="1000", cols="14")
            worksheet_ofertas.append_row([
                "id_oferta", "fecha_scraping", "plataforma_origen", "link_oferta", 
                "titulo_puesto", "empresa", "modalidad", "disponible_hasta", 
                "horario", "departamento", "area_categoria", 
                "descripcion_breve", "requisitos", "beneficios"
            ])
            logger.info("📊 Estructura de pestañas creada (14 columnas)")
        except Exception as e:
            logger.error(f"❌ Error al estructurar hojas: {e}")

    def obtener_busquedas_activas(self) -> list:
        if not self.sheet:
            logger.warning("⚠️ Sin conexión a Sheets. Retornando búsqueda por defecto.")
            return [{"puesto": "practicante de datos", "lugar": "lima"}]
        try:
            try:
                worksheet = self.sheet.worksheet("Config_Busquedas")
            except gspread.WorksheetNotFound:
                worksheet = self.sheet.add_worksheet(title="Config_Busquedas", rows="100", cols="5")
                worksheet.append_row(["Puesto", "Lugar", "Activo", "Ultima_Ejecucion"])
                worksheet.append_row(["practicante de datos", "lima", "SI", "-"])
            
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
            logger.info(f" {len(busquedas_activas)} búsquedas activas encontradas.")
            return busquedas_activas if busquedas_activas else [{"puesto": "practicante de datos", "lugar": "lima"}]
        except Exception as e:
            logger.error(f"❌ Error leyendo configuración: {e}")
            return [{"puesto": "practicante de datos", "lugar": "lima"}]

    def verificar_y_guardar(self, ofertas_del_scraper: list, nombre_scraper: str, puesto: str, lugar: str) -> dict:
        if not ofertas_del_scraper:
            return {'guardadas': 0, 'duplicadas': 0, 'errores': 0}
        if not self.sheet:
            logger.error("❌ Sin conexión a Google Sheets")
            return {'guardadas': 0, 'duplicadas': 0, 'errores': 0}
        
        try:
            hoja_real = self.sheet.worksheet("Ofertas_Extraidas")
            valores_existentes = hoja_real.col_values(1)
            
            filas_a_insertar = []
            contador_nuevas = 0
            contador_duplicadas = 0
            
            for payload in ofertas_del_scraper:
                if payload["id_oferta"] in valores_existentes:
                    contador_duplicadas += 1
                    continue
                
                # ✅ 14 COLUMNAS (sin "nivel")
                fila = [
                    payload.get("id_oferta"),
                    payload.get("fecha_scraping"),
                    payload.get("plataforma_origen"),
                    payload.get("link_oferta"),
                    payload.get("titulo_puesto"),
                    payload.get("empresa"),
                    payload.get("modalidad"),
                    payload.get("disponible_hasta"),
                    payload.get("horario"),
                    payload.get("departamento"),
                    payload.get("area_categoria"),
                    payload.get("descripcion_breve"),
                    payload.get("requisitos"),
                    payload.get("beneficios")
                ]
                filas_a_insertar.append(fila)
                contador_nuevas += 1
            
            if filas_a_insertar:
                hoja_real.append_rows(filas_a_insertar, value_input_option="RAW")
                logger.info(f"💾 {contador_nuevas} ofertas guardadas")
            
            self.actualizar_estado(puesto, lugar)
            
            return {
                'guardadas': contador_nuevas,
                'duplicadas': contador_duplicadas,
                'errores': 0
            }
        except Exception as e:
            logger.error(f"❌ Error guardando ofertas: {e}")
            return {'guardadas': 0, 'duplicadas': 0, 'errores': len(ofertas_del_scraper)}

    def actualizar_estado(self, puesto: str, lugar: str):
        if not self.sheet:
            return
        try:
            worksheet = self.sheet.worksheet("Config_Busquedas")
            registros = worksheet.get_all_values()
            for i, row in enumerate(registros):
                if i > 0 and len(row) >= 2:
                    if row[0].lower() == puesto.lower() and row[1].lower() == lugar.lower():
                        worksheet.update_cell(i+1, 4, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        break
        except Exception as e:
            logger.error(f"❌ Error actualizando estado: {e}")

class SheetsHandlerSimulado:
    def obtener_busquedas_activas(self):
        return [{"puesto": "practicante de datos", "lugar": "lima"}]
    
    def verificar_y_guardar(self, ofertas_del_scraper: list, nombre_scraper: str, puesto: str, lugar: str) -> dict:
        logger.info(f" Modo simulación: {len(ofertas_del_scraper)} ofertas no guardadas")
        return {'guardadas': 0, 'duplicadas': 0, 'errores': 0}
    
    def actualizar_estado(self, puesto: str, lugar: str):
        pass
