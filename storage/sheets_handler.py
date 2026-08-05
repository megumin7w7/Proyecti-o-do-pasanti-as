"""
Módulo: storage/sheets_handler.py
Persistencia en Google Sheets con caché de IDs y rate-limit protection.
"""
import os
import json
import time
from typing import List, Dict
from datetime import datetime
from loguru import logger

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSHEETS_OK = True
except ImportError:
    GSHEETS_OK = False

from config.settings import GOOGLE_SHEET_NAME, CREDENTIALS_FILE, DEST_COLUMNS


class SheetsHandlerSimulado:
    def __init__(self):
        logger.warning("⚠️ Modo Simulación de Sheets activo.")

    def obtener_busquedas_activas(self) -> List[dict]:
        return [{"puesto": "practicante de datos", "lugar": "lima"}]

    def verificar_y_guardar(self, ofertas_del_scraper: list, nombre_scraper: str, puesto: str, lugar: str) -> dict:
        total = len(ofertas_del_scraper) if ofertas_del_scraper else 0
        logger.info(f"📊 [Simulación] {total} ofertas procesadas localmente.")
        return {'guardadas': 0, 'duplicadas': 0, 'errores': 0}

    def actualizar_estado(self, puesto: str, lugar: str):
        pass


class SheetsHandler:
    def __init__(self):
        self.client = None
        self.sheet = None
        self.ids_cacheados = set()
        self._conectar()

    def _conectar(self):
        if not GSHEETS_OK:
            logger.error("❌ gspread no instalado.")
            return

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            try:
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                self.client = gspread.authorize(creds)
                self._abrir_hoja()
                return
            except Exception as e:
                logger.error(f"❌ Error con GOOGLE_CREDENTIALS_JSON: {e}")

        if os.path.exists(CREDENTIALS_FILE):
            try:
                creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
                self.client = gspread.authorize(creds)
                self._abrir_hoja()
                return
            except Exception as e:
                logger.error(f"❌ Error con archivo local {CREDENTIALS_FILE}: {e}")

        logger.warning("⚠️ No se encontraron credenciales válidas.")

    def _abrir_hoja(self):
        try:
            self.sheet = self.client.open(GOOGLE_SHEET_NAME)
            logger.info(f"✅ Conectado a: '{GOOGLE_SHEET_NAME}'")
            self._asegurar_estructura()
            self._cargar_cache_ids()
        except Exception as e:
            logger.error(f"❌ Error abriendo hoja: {e}")

    def _asegurar_estructura(self):
        if not self.sheet:
            return
        try:
            self.sheet.worksheet("Config_Busquedas")
        except gspread.WorksheetNotFound:
            ws = self.sheet.add_worksheet("Config_Busquedas", rows="100", cols="4")
            ws.append_row(["Puesto", "Lugar", "Activo", "Ultima_Ejecucion"])
            ws.append_row(["practicante de datos", "lima", "SI", "-"])

        try:
            self.sheet.worksheet("Ofertas_Extraidas")
        except gspread.WorksheetNotFound:
            ws = self.sheet.add_worksheet("Ofertas_Extraidas", rows="1000", cols=str(len(DEST_COLUMNS)))
            ws.append_row(DEST_COLUMNS)

    def _cargar_cache_ids(self):
        try:
            hoja = self.sheet.worksheet("Ofertas_Extraidas")
            ids = hoja.col_values(1)
            self.ids_cacheados = set(ids[1:])
            logger.info(f"⚡ Caché cargada: {len(self.ids_cacheados)} ofertas.")
        except Exception as e:
            logger.warning(f"No se pudo cargar caché: {e}")

    def obtener_busquedas_activas(self) -> List[dict]:
        if not self.sheet:
            return [{"puesto": "practicante de datos", "lugar": "lima"}]

        try:
            ws = self.sheet.worksheet("Config_Busquedas")
            registros = ws.get_all_records()
            activas = []
            for r in registros:
                puesto = str(r.get("Puesto", "")).strip()
                lugar = str(r.get("Lugar", "lima")).strip().lower().replace(" ", "-")
                activo = str(r.get("Activo", "")).strip().upper()
                if puesto and activo == "SI":
                    activas.append({"puesto": puesto, "lugar": lugar})
            return activas if activas else [{"puesto": "practicante de datos", "lugar": "lima"}]
        except Exception as e:
            logger.error(f"❌ Error leyendo configuración: {e}")
            return [{"puesto": "practicante de datos", "lugar": "lima"}]

    def verificar_y_guardar(self, ofertas_del_scraper: list, nombre_scraper: str, puesto: str, lugar: str) -> dict:
        if not ofertas_del_scraper:
            return {'guardadas': 0, 'duplicadas': 0, 'errores': 0}
        if not self.sheet:
            return {'guardadas': 0, 'duplicadas': 0, 'errores': len(ofertas_del_scraper)}

        filas = []
        nuevas, duplicadas = 0, 0

        try:
            hoja = self.sheet.worksheet("Ofertas_Extraidas")
            for payload in ofertas_del_scraper:
                if payload.get("id_oferta") in self.ids_cacheados:
                    duplicadas += 1
                    continue

                fila = [payload.get(c, "") for c in DEST_COLUMNS]
                filas.append(fila)
                self.ids_cacheados.add(payload["id_oferta"])
                nuevas += 1

            if filas:
                for i in range(0, len(filas), 50):
                    chunk = filas[i:i+50]
                    hoja.append_rows(chunk, value_input_option="RAW")
                    if i + 50 < len(filas):
                        time.sleep(1)
                logger.info(f"💾 Guardadas {nuevas} ofertas nuevas.")

            self.actualizar_estado(puesto, lugar)
            return {'guardadas': nuevas, 'duplicadas': duplicadas, 'errores': 0}

        except Exception as e:
            logger.error(f"❌ Error guardando en Sheets: {e}")
            return {'guardadas': 0, 'duplicadas': duplicadas, 'errores': len(ofertas_del_scraper)}

    def actualizar_estado(self, puesto: str, lugar: str):
        if not self.sheet:
            return
        try:
            ws = self.sheet.worksheet("Config_Busquedas")
            registros = ws.get_all_values()
            puesto_norm = puesto.lower().strip()
            lugar_norm = lugar.lower().strip().replace(" ", "-")

            for i, row in enumerate(registros):
                if i == 0:
                    continue
                if len(row) >= 2:
                    r_puesto = row[0].lower().strip()
                    r_lugar = row[1].lower().strip().replace(" ", "-")
                    if r_puesto == puesto_norm and r_lugar == lugar_norm:
                        ws.update_cell(i + 1, 4, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        break
        except Exception:
            pass
