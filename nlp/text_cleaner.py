"""
Módulo: text_cleaner.py
Propósito: Limpieza básica de texto crudo extraído de HTML.
No hace NLP ni extracción semántica (eso lo hace ai_extractor.py).
"""
import re


class TextCleaner:
    """
    Limpia texto crudo de HTML eliminando URLs, estandarizando
    saltos de línea y viñetas.
    """
    
    def limpiar_texto(self, texto_crudo: str) -> str:
        """
        Limpia un texto crudo y devuelve una versión normalizada.
        
        Args:
            texto_crudo: Texto extraído directamente del navegador
            
        Returns:
            Texto limpio y normalizado
        """
        if not texto_crudo:
            return ""
        
        # 1. Eliminar URLs (http, https, www)
        texto = re.sub(r'https?://\S+|www\.\S+', '', texto_crudo)
        
        # 2. Estandarizar saltos de línea
        texto = texto.replace('\r\n', '\n').replace('\r', '\n')
        
        # 3. Estandarizar viñetas (bullet points) a formato "- "
        texto = re.sub(
            r'^[ \t][•✔*\-\u2013\u2014][ \t]', 
            '- ', 
            texto, 
            flags=re.MULTILINE
        )
        
        return texto.strip()


# ==========================================
# BLOQUE DE PRUEBA (solo se ejecuta si corres este archivo directamente)
# ==========================================
if __name__ == "__main__":
    texto_prueba = """
    Practicante de Contabilidad
    CARTAVIO RUM COMPANY S.A.C.
    Requisitos:
    Estudiantes de últimos ciclos o egresados de la carrera de contabilidad.
    BeneficiosSubvención económica competitiva.
    """
    
    cleaner = TextCleaner()
    resultado = cleaner.limpiar_texto(texto_prueba)
    
    print("="*60)
    print("✅ PRUEBA DE TextCleaner")
    print("="*60)
    print(resultado)