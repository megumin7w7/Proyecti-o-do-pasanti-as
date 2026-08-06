"""
Módulo: nlp/ai_extractor.py
Extracción de entidades con spaCy. Fallback si no está disponible.
"""
import re
import subprocess
import sys
from typing import List, Dict
from loguru import logger

from config.settings import SPACY_MODEL_NAME


class AIExtractor:
    def __init__(self):
        self.nlp = self._cargar_modelo()

    def _cargar_modelo(self):
        try:
            import spacy
            nlp = spacy.load(SPACY_MODEL_NAME)
            logger.info("✅ Modelo spaCy cargado.")
            return nlp
        except OSError:
            logger.warning(f"⚠️ Modelo {SPACY_MODEL_NAME} no encontrado. Descargando...")
            try:
                subprocess.check_call([sys.executable, "-m", "spacy", "download", SPACY_MODEL_NAME])
                import spacy
                return spacy.load(SPACY_MODEL_NAME)
            except Exception as e:
                logger.error(f"❌ No se pudo descargar spaCy: {e}. Usando fallback regex.")
                return None

    def extraer_datos_oferta(self, texto_limpio: str) -> dict:
        if not texto_limpio or len(texto_limpio) < 20:
            return self._resultado_vacio()

        texto = texto_limpio[:12000]
        doc = self.nlp(texto) if self.nlp else None

        requisitos, beneficios = self._minar_secciones(texto)
        requisitos_est = self._clasificar_requisitos(requisitos)

        return {
            "titulo_puesto": self._extraer_titulo(texto),
            "empresa": self._extraer_empresa(doc, texto),
            "modalidad": self._extraer_modalidad(texto),
            "nivel": self._extraer_nivel(texto),
            "horario": self._extraer_horario(texto),
            "departamento": self._extraer_departamento(texto),
            "descripcion_breve": self._extraer_descripcion_breve(texto),
            "beneficios": "\n".join(f"• {b}" for b in beneficios) if beneficios else "• Beneficios de ley.",
            "requisitos": requisitos_est
        }

    def _minar_secciones(self, texto: str) -> tuple:
        lineas = texto.split('\n')
        requisitos, beneficios = [], []
        estado = None

        for linea in lineas:
            s = linea.strip()
            if not s:
                continue
            sl = s.lower()

            # 🚀 ACTUALIZADO: Más palabras clave para detectar Requisitos
            if any(x in sl for x in ["requisito", "perfil", "requerimiento", "qué buscamos", "que buscamos", "lo que aportarás", "buscamostutalento", "conocimientos"]):
                estado = "requisitos"
                continue
            # 🚀 ACTUALIZADO: Más palabras clave para detectar Beneficios
            elif any(x in sl for x in ["beneficio", "ofrecemos", "te ofrecemos", "valoramos tu impacto", "condiciones"]):
                estado = "beneficios"
                continue
            elif any(x in sl for x in ["funciones", "responsabilidades", "actividades", "reto tendrás", "generarás valor"]):
                estado = "funciones"
                continue

            if estado == "requisitos" and len(s) > 5:
                if any(x in sl for x in ["beneficio", "ofrecemos", "funciones", "condiciones"]):
                    continue
                requisitos.append(s)
            elif estado == "beneficios" and len(s) > 5:
                if any(x in sl for x in ["requisito", "perfil", "funciones", "qué buscamos"]):
                    continue
                beneficios.append(s)

        return requisitos, beneficios

    def _clasificar_requisitos(self, reqs: List[str]) -> List[Dict]:
        patrones = ['deseable', 'valorable', 'preferible', 'preferentemente', 'plus', 'sería']
        resultado = []
        for req in reqs:
            rl = req.lower()
            tipo = "Deseable" if any(p in rl for p in patrones) else "Indispensable"
            limpio = re.sub(r'(?i)^(deseable|indispensable|requisito)\s*[:\-]?\s*', '', req).strip()
            resultado.append({"texto": limpio.capitalize(), "tipo": tipo})
        return resultado

    def _extraer_modalidad(self, texto: str) -> str:
        t = texto.lower()
        if any(x in t for x in ['remoto', 'home office', 'desde casa', 'teletrabajo', 'remote']):
            return "Remoto"
        if any(x in t for x in ['hibrido', 'híbrido', 'semipresencial', 'hybrid']):
            return "Híbrido"
        return "Presencial"

    def _extraer_horario(self, texto: str) -> str:
        t = texto.lower()
        if any(x in t for x in ['part time', 'medio tiempo', 'tiempo parcial', 'half time', '4 horas']):
            return "Medio Tiempo"
        return "Tiempo Completo"

    def _extraer_nivel(self, texto: str) -> str:
        t = texto.lower()
        if any(x in t for x in ['practicante', 'practica', 'práctica', 'pre profesional', 'pasantía']):
            return "Práctica"
        if 'trainee' in t:
            return "Trainee"
        if any(x in t for x in ['junior', 'jr', 'entry level']):
            return "Junior"
        if any(x in t for x in ['senior', 'sr', 'lider', 'coordinador']):
            return "Senior"
        return "Practicante"

    def _extraer_departamento(self, texto: str) -> str:
        deps = ["Lima", "Arequipa", "La Libertad", "Piura", "Lambayeque", "Ica", "Ancash", "Cusco", "Callao", "Junín", "San Martín"]
        for dep in deps:
            if re.search(r'\b' + dep + r'\b', texto, re.IGNORECASE):
                return dep
        return "Lima"

    def _extraer_empresa(self, doc, texto: str) -> str:
        lineas = [l.strip() for l in texto.split('\n') if l.strip()]

        # 🧠 SENTIDO COMÚN: Lista negra expansiva (Ahora con basura de LinkedIn)
        basura_empresas = {
            'login', 'ofertas', 'empleos', 'salarios', 'blog', 'linkedin', 
            'marketing', 'publicidad', 'contar', 'of lima', 'selección', 
            'beneficios', 'almuerzo', 'modalidad', 'formación', 'te invitamos', 
            'requisitos', 'únete', 'crear cv', 'volver', 'listado', 'empresa', 
            'evaluaciones', 'descripción', 'buscar', 'bumeran', 'computrabajo',
            'continue', 'brand', 'bachiller', 'egresado', 'postula', 'automotrices',
            'google', 'jump', 'técnico titulado', 'participación', 'reporte', 
            'estudiantes', 'ingreso', 'brandeo', 'prácticas', 'funciones', 'bolsa de empleo',
            'importante empresa', 'administración', 'ing.', 'química', 'industrial',
            'ingeniería', 'confidencial', 'unidos!', 'presencial', 'remoto', 'híbrido',
            'actualizado', 'pasar al contenido principal', 'acerca de', 'accesibilidad',
            'condiciones de uso', 'política de privacidad', 'política de cookies'
        }

        # 🎯 NUEVO CAZADOR: "Somos [Nombre de la Empresa]"
        for linea in lineas[:10]:
            if linea.lower().startswith("somos "):
                candidato = re.split(r'[,|.]', linea)[0].replace("Somos ", "").replace("somos ", "").strip()
                # 🚀 EXCEPCIÓN: ¡Aquí NO usamos la lista negra porque el scraper lo inyectó!
                if 3 < len(candidato) <= 65:
                    # Solo evitamos que atrape frases orgánicas como "Somos una empresa importante..."
                    if "una empresa" not in candidato.lower() and "una importante" not in candidato.lower():
                        return candidato

        # 🎯 FRANCOTIRADOR BUMERAN
        for i, linea in enumerate(lineas):
            if "seguir empresa" in linea.lower() and i >= 1:
                empresa = lineas[i-1]
                if re.match(r'^\d+(\.\d+)?$', empresa) and i >= 2:
                    empresa = lineas[i-2]
                
                if len(empresa) > 2 and not any(b in empresa.lower() for b in basura_empresas):
                    return empresa

        # 1. Intento con spaCy (Modelo de IA)
        if doc:
            for ent in doc.ents:
                if ent.label_ == "ORG":
                    nombre = ent.text.strip()
                    if 3 < len(nombre) <= 40 and not any(x in nombre.lower() for x in basura_empresas):
                        return nombre

        # 2. Intento de respaldo (Fallback)
        for linea in lineas[:15]:
            ll = linea.lower()
            if 3 < len(linea) <= 40 and not any(b in ll for b in basura_empresas):
                return linea.split('-')[0].strip()
                
        return "Confidencial"

    def _extraer_titulo(self, texto: str) -> str:
        lineas = [l.strip() for l in texto.split('\n') if l.strip()]
        
        # 🧠 SENTIDO COMÚN: Lista negra de títulos (Ahora con basura de LinkedIn)
        basura = {
            'login', 'crear cv', 'volver', 'listado', 'ofertas', 'salarios', 
            'empresa', 'evaluaciones', 'descripción', 'actualizado', 
            'hace más de', 'blog', 'publicado', 'días', 'horas', 'bumeran',
            'computrabajo', 'postula', 'bolsa de empleo', 'presencial', 
            'híbrido', 'remoto', 'tiempo completo', 'medio tiempo',
            'pasar al contenido principal', 'acerca de', 'accesibilidad',
            'condiciones de uso', 'política de privacidad'
        }
        
        # 🎯 FRANCOTIRADOR BUMERAN
        for i, linea in enumerate(lineas):
            if "seguir empresa" in linea.lower() and i >= 2:
                candidato = lineas[i-2]
                if len(candidato) > 5 and not any(b in candidato.lower() for b in basura):
                    return candidato
                elif i >= 3:
                    candidato_alt = lineas[i-3]
                    if len(candidato_alt) > 5 and not any(b in candidato_alt.lower() for b in basura):
                        return candidato_alt

        # RESPALDO LEYENDO LÍNEAS
        for l in lineas:
            ll = l.lower()
            if not any(b in ll for b in basura) and 5 < len(l) < 120:
                return l
                
        return "Practicante"
        
    def _extraer_descripcion_breve(self, texto: str) -> str:
        lineas = [l.strip() for l in texto.split('\n') if len(l.strip()) > 20]
        for linea in lineas:
            ll = linea.lower()
            if len(linea) > 80 and not any(x in ll for x in ['requisito:', 'beneficio:', 'ofrecemos:', 'funciones:']):
                desc = re.sub(r'(?i)(beneficios|requisitos|funciones).*', '', linea).strip()
                return desc[:350] + ("..." if len(desc) > 350 else "")
        return " ".join(lineas[:3]) if lineas else ""

    def _resultado_vacio(self) -> dict:
        return {
            "titulo_puesto": "Practicante",
            "empresa": "Importante Empresa en el Sector",
            "modalidad": "Presencial",
            "nivel": "Práctica",
            "horario": "Tiempo Completo",
            "departamento": "Lima",
            "descripcion_breve": "",
            "beneficios": "",
            "requisitos": []
        }
