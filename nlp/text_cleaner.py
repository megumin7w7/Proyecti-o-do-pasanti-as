"""
Módulo: nlp/text_cleaner.py
"""
import re

class TextCleaner:
    URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')
    EMAIL_PATTERN = re.compile(r'\S+@\S+\.\S+')
    BULLET_PATTERN = re.compile(r'^[ \t]*[•✔*\-\u2013\u2014][ \t]*', re.MULTILINE)
    WHITESPACE_PATTERN = re.compile(r'\n{3,}')

    def limpiar_texto(self, texto_crudo: str) -> str:
        if not texto_crudo:
            return ""
            
        texto = texto_crudo

        # 🧹 ELIMINACIÓN DE BASURA ESTRUCTURAL DE PLATAFORMAS (Bumeran y LinkedIn)
        patrones_basura = [
            r'Buscar empleo por puesto o palabra clave.*?Blog',
            r'El contenido de este aviso es propiedad del anunciante.*?u otro motivo\.',
            r'¡[Dd]escarga la app en tu celular!.*?© [Cc]opyright \d{4}-\d{4} [Jj]obint',
            r'Únete a LinkedIn.*?Inicia sesión',
            r'Al hacer clic en «Aceptar y unirse».*?Continue with Google',
            r'Descubre a quién ha contratado.*?para este puesto',
            r'Las recomendaciones duplican tus probabilidades.*?Mira a quién conoces',
            r'Recibe notificaciones sobre nuevos empleos.*?alerta de empleo',
            r'Sé de los primeros \d+ solicitantes',
            r'No especificados'
        ]

        # Borramos los bloques masivos usando DOTALL (para que incluya saltos de línea)
        for patron in patrones_basura:
            texto = re.sub(patron, '', texto, flags=re.IGNORECASE | re.DOTALL)

        # Limpieza estándar
        texto = self.URL_PATTERN.sub('', texto)
        texto = self.EMAIL_PATTERN.sub('', texto)
        texto = texto.replace('\r\n', '\n').replace('\r', '\n')
        texto = self.BULLET_PATTERN.sub('- ', texto)
        texto = self.WHITESPACE_PATTERN.sub('\n\n', texto)
        
        return texto.strip()
