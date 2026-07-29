"""
Módulo: app.py (Dashboard Visual Ultraligero - Solo Lectura y Trigger)
Desplegado en: Streamlit Community Cloud
"""
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import requests
import json

# Configuración de la página
st.set_page_config(page_title="Laboral AI Dashboard", page_icon="📊", layout="wide")

st.title("📊 Dashboard de Ofertas Laborales")
st.markdown("Pipeline automatizado: GitHub Actions hace el trabajo pesado, este dashboard solo muestra los resultados.")

# ==============================================================================
# 1. BOTÓN PARA DISPARAR GITHUB ACTIONS
# ==============================================================================
st.sidebar.header("⚙️ Control del Pipeline")

if st.sidebar.button("🚀 Ejecutar Scraping en Segundo Plano", type="primary"):
    with st.spinner("Enviando orden a GitHub Actions..."):
        github_token = os.environ.get("GITHUB_TOKEN")
        repo_owner = "megumin7w7"  # ⚠️ CAMBIA ESTO por tu usuario real de GitHub si es diferente
        repo_name = "Proyecti-o-do-pasanti-as" # ⚠️ CAMBIA ESTO por el nombre exacto de tu repo
        
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/workflows/scraper.yml/dispatches"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {"ref": "main"}
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 204:
            st.success("✅ ¡Orden enviada! GitHub Actions está procesando las ofertas. Esto tomará unos 2-3 minutos. Recarga la página en un momento para ver los nuevos datos.")
        else:
            st.error(f"❌ Error al contactar a GitHub: {response.status_code} - {response.text}")

st.sidebar.markdown("---")
st.sidebar.info("💡 **Nota:** El scraper leerá automáticamente la configuración (Puesto y Lugar) que tengas marcada como 'SI' en la pestaña `Config_Busquedas` de tu Google Sheet.")

# ==============================================================================
# 2. CARGA DE DATOS DESDE GOOGLE SHEETS
# ==============================================================================
@st.cache_data(ttl=300) # Guarda en caché por 5 minutos
def cargar_datos():
    try:
        import json
        import gspread
        from google.oauth2.service_account import Credentials
        
        # 1. Obtener el secreto de Streamlit
        creds_json = st.secrets.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            st.error("⚠️ No se encontró el secreto GOOGLE_CREDENTIALS_JSON en Settings.")
            return pd.DataFrame()
            
        # 2. Parsear el JSON
        creds_dict = json.loads(creds_json)
        
        # 3. ✅ CAMBIO CLAVE: Usar scopes completos (Spreadsheets + Drive)
        creds = Credentials.from_service_account_info(
            creds_dict, 
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        
        # 4. Conectar y abrir
        client = gspread.authorize(creds)
        
        # ⚠️ IMPORTANTE: El nombre debe ser EXACTO, respetando mayúsculas y guiones bajos
        sheet = client.open("Laboral_AI_Scraper_Data")
        worksheet = sheet.worksheet("Ofertas_Extraidas")
        data = worksheet.get_all_records()
        
        return pd.DataFrame(data)
        
    except gspread.SpreadsheetNotFound:
        st.error("❌ No se encontró la hoja 'Laboral_AI_Scraper_Data'. Verifica que el nombre sea exacto y que hayas compartido el acceso.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {e}")
        return pd.DataFrame()

df = cargar_datos()

# ==============================================================================
# 3. VISUALIZACIÓN DE DATOS
# ==============================================================================
if not df.empty:
    # Convertir fecha a datetime para ordenar
    df['fecha_scraping'] = pd.to_datetime(df['fecha_scraping'], errors='coerce')
    df = df.sort_values(by='fecha_scraping', ascending=False).reset_index(drop=True)
    
    # Métricas principales
    col1, col2, col3 = st.columns(3)
    col1.metric("📈 Total Ofertas", len(df))
    col2.metric("🌐 Plataformas", df['plataforma_origen'].nunique())
    col3.metric("🕒 Última Actualización", df['fecha_scraping'].max().strftime('%d/%m %H:%M') if not pd.isna(df['fecha_scraping'].max()) else "N/A")
    
    st.markdown("---")
    
    # Filtros interactivos
    st.subheader("🔍 Filtros")
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        plataformas = st.multiselect("Plataforma", options=df['plataforma_origen'].unique(), default=df['plataforma_origen'].unique())
    with col_f2:
        departamentos = st.multiselect("Departamento", options=df['departamento'].unique(), default=df['departamento'].unique())
    with col_f3:
        categorias = st.multiselect("Categoría", options=df['area_categoria'].unique(), default=df['area_categoria'].unique())
        
    # Aplicar filtros
    df_filtrado = df[
        (df['plataforma_origen'].isin(plataformas)) & 
        (df['departamento'].isin(departamentos)) & 
        (df['area_categoria'].isin(categorias))
    ]
    
    # Mostrar tabla
    st.subheader(f"📋 Listado de Ofertas ({len(df_filtrado)} resultados)")
    
    # Seleccionar columnas bonitas para mostrar
    columnas_mostrar = ['fecha_scraping', 'plataforma_origen', 'titulo_puesto', 'empresa', 'departamento', 'modalidad', 'link_oferta']
    columnas_existentes = [col for col in columnas_mostrar if col in df_filtrado.columns]
    
    st.dataframe(
        df_filtrado[columnas_existentes],
        use_container_width=True,
        hide_index=True,
        column_config={
            "link_oferta": st.column_config.LinkColumn("Ver Oferta", display_text="🔗 Abrir")
        }
    )
    
    # Botón de descarga
    csv = df_filtrado.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descargar Ofertas Filtradas (CSV)",
        data=csv,
        file_name="ofertas_laborales.csv",
        mime="text/csv"
    )
else:
    st.info("📭 No hay datos disponibles aún. Asegúrate de haber ejecutado el pipeline al menos una vez desde GitHub Actions.")

# Footer
st.markdown("---")
st.caption("Proyecto de Pasantía | Pipeline de Extracción de Ofertas Laborales con IA | Desplegado en Streamlit Community Cloud")
