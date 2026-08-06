import re

def calcular_dias_antiguedad(texto: str) -> int:
    """
    Toma un texto de cualquier plataforma y extrae la antigüedad en días.
    Si no encuentra nada, devuelve 0 para no perder ofertas por error.
    """
    if not texto:
        return 0
        
    t = texto.lower()
    
    # 1. Casos directos
    if 'hoy' in t:
        return 0
    if 'ayer' in t:
        return 1
        
    # 2. Buscar patrón: (hace|más de) [numero] (hora|día|semana|mes)
    # Ej: "hace 3 semanas", "más de 15 días", "hace 2 meses"
    patron = r'(?:hace|más de|mas de)\s*(\d+)\s*(hora|día|dia|semana|mes)'
    match = re.search(patron, t)
    
    if match:
        cantidad = int(match.group(1))
        unidad = match.group(2)
        
        if 'hora' in unidad:
            return 0  # Menos de un día
        elif 'dia' in unidad or 'día' in unidad:
            return cantidad
        elif 'semana' in unidad:
            return cantidad * 7
        elif 'mes' in unidad:
            return cantidad * 30
            
    return 0 # Ante la duda, le damos luz verde
