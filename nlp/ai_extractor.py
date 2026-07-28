import os
import re
import spacy
from loguru import logger

class AIExtractor:
    def __init__(self):
        self.modelo = "es_core_news_md"
        try:
            # Intenta cargar el modelo. Si falla, lo descarga (solo la primera vez en HF)
            self.nlp = spacy.load(self.modelo)
            logger.info("✅ Modelo Spacy cargado exitosamente.")
        except Exception:
            logger.warning(f"⚠️ Modelo {self.modelo} no encontrado. Descargando...")
            os.system(f"python -m spacy download {self.modelo}")
            self.nlp = spacy.load(self.modelo)
            logger.info("✅ Modelo Spacy descargado y cargado.")

    def extraer_datos_oferta(self, texto_limpio: str) -> dict:
        if not texto_limpio or len(texto_limpio) < 20:
            return self._resultado_vacio()
        
        # Fix Python 3.13: (?i) estrictamente al inicio
        texto_limpio = re.sub(r'(?i)(beneficios|requisitos)(subvención|estudiantes|experiencia|\b)', r'\1 \2', texto_limpio)
        
        # Limitar a 12000 caracteres para evitar sobrecarga de memoria en Spacy
        doc = self.nlp(texto_limpio[:12000])
        
        requisitos_lista, beneficios_lista = self._minar_secciones(texto_limpio)
        requisitos_estructurados = self._clasificar_requisitos(requisitos_lista)
        
        beneficios_formateados = "\n".join([f"• {b}" for b in beneficios_lista]) if beneficios_lista else "• Beneficios de ley."
        
        # Extracción de atributos
        modalidad = self._extraer_modalidad(texto_limpio)
        horario = self._extraer_horario(texto_limpio)
        nivel = self._extraer_nivel(texto_limpio)
        departamento = self._extraer_departamento(texto_limpio)
        titulo = self._extraer_titulo(texto_limpio)
        empresa = self._extraer_empresa(doc, texto_limpio, titulo)
        
        # Descripción breve inteligente
        desc_breve = self._extraer_descripcion_breve(texto_limpio)
        
        return {
            "titulo_puesto": titulo,
            "empresa": empresa,
            "modalidad": modalidad,
            "nivel": nivel,
            "horario": horario,
            "departamento": departamento,
            "descripcion_breve": desc_breve,
            "beneficios": beneficios_formateados,
            "requisitos": requisitos_estructurados
        }

    def _minar_secciones(self, texto: str) -> tuple:
        lineas = texto.split('\n')
        requisitos, beneficios = [], []
        estado_actual = None
        
        for linea in lineas:
            linea_s = linea.strip()
            if not linea_s: continue
            linea_lower = linea_s.lower()
            
            if "requisito" in linea_lower or "perfil" in linea_lower:
                estado_actual = "requisitos"
                continue
            elif "beneficio" in linea_lower or "ofrecemos" in linea_lower:
                estado_actual = "beneficios"
                continue
            elif any(x in linea_lower for x in ["misión:", "responsabilidades:", "funciones:"]):
                estado_actual = "funciones"
                continue
                
            if estado_actual == "requisitos" and len(linea_s) > 5:
                if any(x in linea_lower for x in ["beneficio", "ofrecemos", "funciones"]): break
                requisitos.append(linea_s)
            elif estado_actual == "beneficios" and len(linea_s) > 5:
                if any(x in linea_lower for x in ["requisito", "perfil"]): break
                beneficios.append(linea_s)
                
        return requisitos, beneficios

    def _clasificar_requisitos(self, requisitos_lista: list) -> list:
        estructurados = []
        patrones_deseable = ['deseable', 'valorable', 'preferible', 'preferentemente', 'plus']
        
        for req in requisitos_lista:
            req_lower = req.lower()
            tipo = "Indispensable" if not any(p in req_lower for p in patrones_deseable) else "Deseable"
            req_limpio = re.sub(r'(?i)^(deseable|indispensable|requisito)\s*[:\-]?\s*', '', req).strip()
            estructurados.append({"texto": req_limpio.capitalize(), "tipo": tipo})
            
        return estructurados

    def _extraer_modalidad(self, texto: str) -> str:
        t = texto.lower()
        if any(x in t for x in ['remoto', 'home office', 'desde casa']): return "Remoto"
        if any(x in t for x in ['hibrido', 'híbrido', 'semipresencial']): return "Híbrido"
        return "Presencial"

    def _extraer_horario(self, texto: str) -> str:
        if any(x in texto.lower() for x in ['part time', 'medio tiempo', 'tiempo parcial']): return "Medio Tiempo"
        return "Tiempo Completo"

    def _extraer_nivel(self, texto: str) -> str:
        t = texto.lower()
        if any(x in t for x in ['practicante', 'practica', 'práctica', 'pre profesional']): return "Práctica"
        if 'trainee' in t: return "Trainee"
        if 'junior' in t or 'jr' in t: return "Junior"
        return "Practicante"

    def _extraer_departamento(self, texto: str) -> str:
        departamentos = ["Lima", "Arequipa", "La Libertad", "Piura", "Lambayeque", "Ica", "Ancash", "Cusco", "Callao"]
        for dep in departamentos:
            if re.search(r'\b' + dep + r'\b', texto, re.IGNORECASE):
                return dep
        return "Lima"

    def _extraer_empresa(self, doc, texto: str, titulo: str) -> str:
        lineas = [l.strip() for l in texto.split('\n') if l.strip()]
        basura_ui = ['login', 'crear cv', 'volver', 'listado', 'ofertas', 'salarios', 'empresa', 'evaluaciones', 'descripción']
        for linea in lineas[:15]:
            l_lower = linea.lower()
            if l_lower != titulo.lower() and not any(b in l_lower for b in basura_ui) and len(linea) > 3:
                return linea.split('-')[0].strip()
        return "Confidencial"

    def _extraer_titulo(self, texto: str) -> str:
        lineas = [l.strip() for l in texto.split('\n') if l.strip()]
        basura_ui = ['login', 'crear cv', 'volver', 'listado', 'ofertas', 'salarios', 'empresa', 'evaluaciones', 'descripción']
        for l in lineas:
            l_lower = l.lower()
            if not any(b in l_lower for b in basura_ui) and len(l) > 8:
                return l
        return "Practicante"

    def _extraer_descripcion_breve(self, texto_limpio: str) -> str:
        lineas = [l.strip() for l in texto_limpio.split('\n') if len(l.strip()) > 0]
        desc_breve = ""
        for linea in lineas:
            if len(linea) > 80 and not any(x in linea.lower() for x in ['requisito:', 'beneficio:', 'ofrecemos:', 'funciones:']):
                desc_breve = linea
                break
        if not desc_breve:
            desc_breve = " ".join(lineas[4:7]) if len(lineas) >= 7 else " ".join(lineas)
        desc_breve = re.sub(r'(?i)(beneficios|requisitos|funciones).*', '', desc_breve).strip()
        return desc_breve[:350] + ("..." if len(desc_breve) > 350 else "")

    def _resultado_vacio(self) -> dict:
        return {
            "titulo_puesto": "Practicante", "empresa": "Confidencial", "modalidad": "Presencial", 
            "nivel": "Práctica", "horario": "Tiempo Completo", "departamento": "Lima", 
            "descripcion_breve": "", "beneficios": "", "requisitos": []
        }