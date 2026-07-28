"""
Módulo: app.py (Interfaz Streamlit para Hugging Face Spaces)
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from main import ejecutar_pipeline

# Configurar página
st.set_page_config(
    page_title="Job Scraper Pipeline",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título
st.title("💼 Dashboard de Recolección de Ofertas Laborales")
st.markdown("---")

# ============================================================
# SIDEBAR: CONFIGURACIÓN
# ============================================================
st.sidebar.header("️ Configuración")

puesto = st.sidebar.text_input("Puesto a buscar", "practicante de datos")
lugar = st.sidebar.text_input("Ubicación", "lima")
limite = st.sidebar.number_input("Límite de ofertas por scraper", min_value=5, max_value=200, value=20)

st.sidebar.subheader("🔧 Scrapers a activar")
usar_bumeran = st.sidebar.checkbox("Bumeran", value=True)
usar_computrabajo = st.sidebar.checkbox("Computrabajo", value=True)
usar_linkedin = st.sidebar.checkbox("LinkedIn", value=False)
usar_indeed = st.sidebar.checkbox("Indeed", value=False)

st.sidebar.subheader(" Procesamiento NLP")
usar_nlp = st.sidebar.checkbox("Filtrar con IA (Spacy)", value=True)

# ============================================================
# CUERPO PRINCIPAL
# ============================================================

# Estado de ejecución
if 'ejecutando' not in st.session_state:
    st.session_state.ejecutando = False
if 'resultados' not in st.session_state:
    st.session_state.resultados = None

# Callback para actualizar progreso
def actualizar_progreso(actual, total, mensaje):
    st.session_state.progreso_actual = actual
    st.session_state.progreso_total = total
    st.session_state.progreso_mensaje = mensaje

# Botón de ejecución
if st.button("🚀 Iniciar Extracción", type="primary", disabled=st.session_state.ejecutando):
    st.session_state.ejecutando = True
    st.session_state.resultados = None
    st.session_state.progreso_actual = 0
    st.session_state.progreso_total = len([x for x in [usar_bumeran, usar_computrabajo, usar_linkedin, usar_indeed] if x])
    st.session_state.progreso_mensaje = "Iniciando..."
    
    # Ejecutar pipeline
    with st.spinner("Ejecutando pipeline..."):
        resultados = ejecutar_pipeline(
            puesto=puesto,
            lugar=lugar,
            limite_ofertas=limite,
            usar_bumeran=usar_bumeran,
            usar_computrabajo=usar_computrabajo,
            usar_linkedin=usar_linkedin,
            usar_indeed=usar_indeed,
            usar_nlp=usar_nlp,
            progress_callback=actualizar_progreso
        )
        
        st.session_state.resultados = resultados
        st.session_state.ejecutando = False

# Mostrar progreso
if st.session_state.ejecutando:
    st.info(f" {st.session_state.progreso_mensaje}")
    if st.session_state.progreso_total > 0:
        st.progress(st.session_state.progreso_actual / st.session_state.progreso_total)

# Mostrar resultados
if st.session_state.resultados:
    resultados = st.session_state.resultados
    
    if resultados['success']:
        st.success(f"✅ Pipeline completado: {resultados['total_ofertas']} ofertas guardadas")
        
        # Mostrar estadísticas por scraper
        st.subheader("📊 Resultados por Scraper")
        
        datos_tabla = []
        for scraper, stats in resultados['resultados_por_scraper'].items():
            datos_tabla.append({
                'Scraper': scraper,
                'Extraídas': stats.get('extraidas', 0),
                'Guardadas': stats.get('guardadas', 0),
                'Duplicadas': stats.get('duplicadas', 0),
                'Errores': stats.get('errores', 0)
            })
        
        if datos_tabla:
            df_resultados = pd.DataFrame(datos_tabla)
            st.dataframe(df_resultados, use_container_width=True)
        
        # Información adicional
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Guardadas", resultados['total_ofertas'])
        with col2:
            st.metric("Tiempo de Ejecución", f"{resultados['tiempo_ejecucion']:.2f}s")
        
        # Mostrar payloads (opcional, para debugging)
        with st.expander("🔍 Ver ofertas procesadas (debugging)"):
            if resultados['payloads']:
                df_payloads = pd.DataFrame(resultados['payloads'])
                st.dataframe(df_payloads, use_container_width=True)
                
                # Botón de descarga
                csv = df_payloads.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=" Descargar CSV",
                    data=csv,
                    file_name=f"ofertas_{puesto.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No hay ofertas para mostrar")
    
    else:
        st.error(f"❌ Error: {resultados.get('error')}")

# Footer
st.markdown("---")
st.markdown("**Proyecto de Pasantía** | Pipeline de Extracción de Ofertas Laborales con IA")