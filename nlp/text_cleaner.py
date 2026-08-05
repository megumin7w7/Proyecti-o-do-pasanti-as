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

        texto = self.URL_PATTERN.sub('', texto_crudo)
        texto = self.EMAIL_PATTERN.sub('', texto)
        texto = texto.replace('\r\n', '\n').replace('\r', '\n')
        texto = self.BULLET_PATTERN.sub('- ', texto)
        texto = self.WHITESPACE_PATTERN.sub('\n\n', texto)
        return texto.strip()
