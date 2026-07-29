<div align="center">

# Laboral.AI — Job Scraper Inteligente
### Proyecto de Pasantía 2026 | Pipeline de Extracción y Análisis de Ofertas Laborales

<img src="https://readme-typing-svg.herokuapp.com?font=Lexend+Giga&size=24&pause=1000&color=4A90E2&center=true&vCenter=true&width=700&lines=+%7C+NLP+%7C+IA;Python+%7C+Selenium+%7C+Playwright+%7C+Streamlit;Arteaga+Guerra%2C+Pedro+Sebastian" />

<br>

![Python](https://img.shields.io/badge/Python-3.13-blue?style=for-the-badge&logo=python)
![Selenium](https://img.shields.io/badge/Selenium-4.15-43B02A?style=for-the-badge&logo=selenium)
![Playwright](https://img.shields.io/badge/Playwright-1.40-2EAD33?style=for-the-badge&logo=playwright)
![Streamlit](https://img.shields.io/badge/Streamlit-1.31-FF4B4B?style=for-the-badge&logo=streamlit)
![Spacy](https://img.shields.io/badge/spaCy-3.7-09A3D5?style=for-the-badge&logo=spacy)
![Status](https://img.shields.io/badge/Status-En+Desarrollo-yellow?style=for-the-badge)

</div>

---

## 📋 Información del Proyecto

| Campo | Detalle |
|---|---|
| **Autor** | Alfieri Arteaga, Pedro Sebastian |
| **Tipo** | Proyecto de Pasantía Profesional |
| **Institución** | Laboral.AI |
| **Tecnología** | Python, Selenium, Playwright, Streamlit, NLP |
| **Año** | 2026 |
| **Estado** | Pipeline funcional con despliegue en Hugging Face |

---

## 📖 Descripción General

**Laboral.AI Job Scraper** es un pipeline automatizado de extracción, procesamiento y análisis de ofertas laborales desde las principales bolsas de trabajo del Perú (Computrabajo, Bumeran, LinkedIn e Indeed). 

El sistema combina:
-  **Web Scraping** multiplataforma con Selenium y Playwright
-  **Procesamiento de Lenguaje Natural (NLP)** con spaCy para extracción semántica
-  **Análisis inteligente** de requisitos, beneficios y compatibilidad de perfiles
-  **Persistencia automatizada** en Google Sheets con detección de duplicados
-  **Dashboard interactivo** en Streamlit para visualización y control del pipeline

### Casos de Uso Principales:
1. **Búsqueda masiva de empleo:** Extracción automatizada de vacantes por puesto y ubicación
2. **Análisis de mercado laboral:** Identificación de skills más demandadas y brechas de talento
3. **Matching candidato-puesto:** Evaluación de compatibilidad entre CVs y requisitos de puestos
4. **Inteligencia competitiva:** Monitoreo de tendencias salariales y modalidades de trabajo

---

## 🚀 Características Principales

###  Scraping Multiplataforma
| Plataforma | Tecnología | Características |
|---|---|---|
| **Computrabajo** | Selenium | Paginación dinámica, filtrado por ubicación, extracción completa |
| **Bumeran** | Selenium | Navegación por páginas, filtros React, anti-bloqueo |
| **LinkedIn** | Selenium | Búsqueda avanzada, extracción de descripciones completas |
| **Indeed** | Playwright | Stealth mode, bypass de CAPTCHA Cloudflare, perfil persistente |

### 🧠 Procesamiento NLP con IA
- **Limpieza inteligente:** Eliminación de URLs, estandarización de viñetas, separación de secciones
- **Extracción semántica:** 
  - Clasificación de requisitos (Indispensable vs Deseable)
  - Detección de beneficios y compensaciones
  - Extracción de modalidad, horario, nivel y departamento
  - Identificación de empresa y descripción breve
- **Validación de relevancia:** Filtrado semántico por área (Marketing, Datos, etc.)

###  Persistencia Inteligente
- **Google Sheets API:** Almacenamiento estructurado en 15 columnas
- **Anti-duplicados:** Detección por ID único (hash de URL + plataforma)
- **Batch processing:** Inserción masiva optimizada
- **Modo simulación:** Fallback cuando no hay credenciales

###  Dashboard Streamlit
- **Configuración interactiva:** Selección de portales, puesto, ubicación y límite
- **Monitoreo en tiempo real:** Barra de progreso y logs del pipeline
- **Visualización de resultados:** Tablas dinámicas por scraper
- **Exportación CSV:** Descarga directa de ofertas procesadas

---

## 🛠️ Tecnologías Utilizadas

| Categoría | Herramientas |
|---|---|
| **Lenguaje** | Python 3.13 |
| **Web Scraping** | Selenium 4.15, Playwright 1.40, webdriver-manager |
| **NLP** | spaCy 3.7 (es_core_news_md), regex |
| **Dashboard** | Streamlit 1.31, Pandas 2.1 |
| **Persistencia** | gspread, Google Sheets API, google-auth |
| **Contenedor** | Docker (para Hugging Face Spaces) |
| **Logging** | loguru |
| **Utilidades** | python-dotenv, hashlib, json, os, re |

---

## 📦 Instalación y Configuración

### Requisitos Previos
Python 3.11 o superior
python --version
Git
git --version

### Paso 1: Clonar el Repositorio
```bash
git clone https://github.com/[tu-usuario]/PROYECTIÑO_DO_PASANTIÑAS.git
cd PROYECTIÑO_DO_PASANTIÑAS
