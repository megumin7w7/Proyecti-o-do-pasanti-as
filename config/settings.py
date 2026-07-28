"""
CONFIGURACIÓN GLOBAL DEL PROYECTO
"""
import os
from typing import Final
from dotenv import load_dotenv

load_dotenv()

SPACY_MODEL_NAME: Final[str] = "es_core_news_md"
MODELO_ENTRENADO_PATH: Final[str] = os.path.join("nlp", "modelo_laboral_ner")

GOOGLE_SHEET_NAME: Final[str] = "Laboral_AI_Scraper_Data"
CREDENTIALS_FILE: Final[str] = os.path.join("config", "credentials.json")

HEADLESS_MODE: Final[bool] = True  # ✅ True para producción
TIMEOUT_SECONDS: Final[int] = 15

REQUEST_TIMEOUT = TIMEOUT_SECONDS
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
MAX_RETRIES = 3
DELAY_BETWEEN_REQUESTS = 2

# ✅ 14 COLUMNAS (sin "nivel")
DEST_COLUMNS = [
    'id_oferta', 'fecha_scraping', 'plataforma_origen', 'link_oferta',
    'titulo_puesto', 'empresa', 'modalidad', 'disponible_hasta',
    'horario', 'departamento', 'area_categoria',
    'descripcion_breve', 'requisitos', 'beneficios'
]
