import os
from typing import Final
from dotenv import load_dotenv

load_dotenv()

# NLP
SPACY_MODEL_NAME: Final[str] = "es_core_news_md"

# Google Sheets (Soporta Variable de Entorno de Hugging Face)
GOOGLE_SHEET_NAME: Final[str] = "Laboral_AI_Scraper_Data"
CREDENTIALS_FILE: Final[str] = os.path.join("config", "credentials.json")

# SCRAPER: En Hugging Face SIEMPRE debe ser True
HEADLESS_MODE: Final[bool] = os.getenv("HEADLESS_MODE", "True").lower() == "true"
TIMEOUT_SECONDS: Final[int] = 15

REQUEST_TIMEOUT = TIMEOUT_SECONDS
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
MAX_RETRIES = 3
DELAY_BETWEEN_REQUESTS = 2

DEST_COLUMNS = [
    'id_oferta', 'fecha_scraping', 'plataforma_origen', 'link_oferta',
    'titulo_puesto', 'empresa', 'modalidad', 'disponible_hasta',
    'nivel', 'horario', 'departamento', 'area_categoria',
    'descripcion_breve', 'requisitos', 'beneficios'
]