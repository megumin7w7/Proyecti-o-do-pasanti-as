"""
Módulo: utils/url_cleaner.py
Normalización de términos de búsqueda para URLs de portales de empleo.
"""
import re
import unicodedata

def normalizar_termino_busqueda(texto: str) -> dict:
    """
    Toma un texto como 'Ingeniería en Sistemas' y genera slugs seguros para URLs.
    Retorna un diccionario con variaciones para cada plataforma.
    """
    if not texto:
        return {"raw": "", "limpio": "", "slug_guiones": "", "slug_mas": ""}
    
    # 1. Eliminar acentos y diacríticos (ej. 'ía' -> 'ia')
    texto_sin_acentos = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()
    
    # 2. Limpiar caracteres no alfanuméricos
    limpio = re.sub(r'[^a-z0-9\s]', '', texto_sin_acentos)
    limpio = re.sub(r'\s+', ' ', limpio) # Eliminar espacios dobles
    
    return {
        "raw": texto,
        "limpio": limpio,
        "slug_guiones": limpio.replace(" ", "-"),  # Para Computrabajo / Bumeran (ej: ingenieria-en-sistemas)
        "slug_mas": limpio.replace(" ", "+")        # Para Indeed / LinkedIn (ej: ingenieria+en+sistemas)
    }
