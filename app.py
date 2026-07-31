"""
Módulo: app.py (Dashboard Visual Estable con gestión de búsquedas)
"""
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import json

# Configuración de la página
st.set_page_config(page_title="Laboral AI Dashboard", page_icon="📊", layout="wide")

st.title("📊 Dashboard de Ofertas Laborales")
st.markdown("Pipeline automatizado: GitHub Actions hace el trabajo pesado, este dashboard muestra los resultados.")

# ==============================================================================
# 1. FUNCIÓN CENTRALIZADA DE AUTENTICACIÓN (Evita errores 403)
# ==============================================================================
@st.cache_resource
def get_sheets_client():
    """Obtiene un cliente de Google Sheets con permisos completos para leer y escribir."""
    try:
        creds_json = st.secrets.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            return None
        creds_dict = json.loads(creds_json)
        # Usamos el scope completo para evitar conflictos entre lectura y escritura
        creds = Credentials.from_service_account_info(creds_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets"
        ])
        return gspread.authorize(creds)
    except Exception as e:
        st.sidebar.error(f"Error de autenticación: {e}")
        return None

# ==============================================================================
# 2. GESTIÓN DE BÚSQUEDAS DESDE LA WEB
# ==============================================================================
st.sidebar.header("⚙️ Control del Pipeline")

# Sección para agregar nuevas búsquedas
with st.sidebar.expander("➕ Agregar Nueva Búsqueda", expanded=False):
    st.write("Agrega puestos y ubicaciones para buscar")
    
    col1, col2 = st.columns(2)
    with col1:
        nuevo_puesto = st.text_input("Puesto", placeholder="Ej: Practicante marketing")
    with col2:
        nuevo_lugar = st.text_input("Ubicación", placeholder="Ej: Lima", value="Lima")
    
    if st.button("Agregar Búsqueda", type="primary", use_container_width=True):
        if nuevo_puesto and nuevo_lugar:
            client = get_sheets_client()
            if client:
                try:
                    sheet = client.open("Laboral_AI_Scraper_Data")
                    try:
                        config_sheet = sheet.worksheet("Config_Busquedas")
                    except gspread.WorksheetNotFound:
                        config_sheet = sheet.add_worksheet(title="Config_Busquedas", rows="100", cols="4")
                        config_sheet.append_row(["Puesto", "Lugar", "Activo", "Ultima_Ejecucion"])
                    
                    # Agregar nueva búsqueda marcada como "SI"
                    config_sheet.append_row([nuevo_puesto.strip(), nuevo_lugar.strip(), "SI", "-"])
                    st.success(f"✅ Búsqueda agregada: '{nuevo_puesto}' en '{nuevo_lugar}'")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al agregar: {e}")

# Sección para ver/eliminar búsquedas existentes
with st.sidebar.expander("📋 Búsquedas Activas", expanded=True):
    client = get_sheets_client()
    if client:
        try:
            sheet = client.open("Laboral_AI_Scraper_Data")
            try:
                config_sheet = sheet.worksheet("Config_Busquedas")
                busquedas_data = config_sheet.get_all_records()
                busquedas_df = pd.DataFrame(busquedas_data)
                
                if not busquedas_df.empty and 'Puesto' in busquedas_df.columns:
                    # Filtrar solo las activas
                    busquedas_activas = busquedas_df[busquedas_df['Activo'].astype(str).str.upper() == 'SI']
                    
                    if busquedas_activas.empty:
                        st.info("No hay búsquedas activas configuradas.")
                    else:
                        for idx, row in busquedas_activas.iterrows():
                            col_a, col_b = st.columns([4, 1])
                            with col_a:
                                st.text(f"📍 {row['Puesto']} - {row['Lugar']}")
                            with col_b:
                                # Botón para eliminar (marcar como NO de forma segura)
                                if st.button("🗑️", key=f"del_{idx}"):
                                    try:
                                        # Buscamos la celda exacta por el nombre del puesto para evitar errores de índice
                                        cell = config_sheet.find(row['Puesto'])
                                        if cell:
                                            # La columna "Activo" es la 3ra (C)
                                            config_sheet.update_cell(cell.row, 3, "NO")
                                            st.success("✅ Eliminada")
                                            st.rerun()
                                    except Exception as e:
                                        st.error(f"Error al eliminar: {e}")
                else:
                    st.info("No hay búsquedas configuradas aún.")
            except gspread.WorksheetNotFound:
                st.info("No hay pestaña 'Config_Busquedas'. Agrega una búsqueda para crearla.")
        except Exception as e:
            st.sidebar.error(f"Error cargando búsquedas: {e}")
    else:
        st.sidebar.error("No se pudo conectar a Google Sheets. Verifica tus secretos.")

# Botón para ejecutar scraping
if st.sidebar.button("🚀 Ejecutar Scraping en Segundo Plano", type="primary", use_container_width=True):
    with st.spinner("Enviando orden a GitHub Actions..."):
        github_token = st.secrets.get("GITHUB_TOKEN")
        repo_owner = "megumin7w7"  # ⚠️ CAMBIA ESTO por tu usuario real de GitHub
        repo_name = "Proyecti-o-do-pasanti-as"  # ⚠️ CAMBIA ESTO por tu repositorio real
        
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/workflows/scraper.yml/dispatches"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {"ref": "main"}
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 204:
            st.success("✅ ¡Orden enviada! GitHub Actions está procesando. Recarga en 5-10 minutos.")
        else:
            st.error(f"❌ Error: {response.status_code} - {response.text}")

st.sidebar.markdown("---")
st.sidebar.info("💡 **Nota:** Las búsquedas se guardan automáticamente en tu Google Sheet (pestaña Config_Busquedas)")

# ==============================================================================
# 3. CARGA DE DATOS DESDE GOOGLE SHEETS
# ==============================================================================
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        client = get_sheets_client()
        if not client:
            return pd.DataFrame()
            
        sheet = client.open("Laboral_AI_Scraper_Data")
        worksheet = sheet.worksheet("Ofertas_Extraidas")
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"❌ Error conectando a Google Sheets: {e}")
        return pd.DataFrame()

df = cargar_datos()

# ==============================================================================
# 4. VISUALIZACIÓN DE DATOS Y FILTROS
# ==============================================================================
if not df.empty:
    # Convertir fecha a datetime
    if 'fecha_scraping' in df.columns:
        df['fecha_scraping'] = pd.to_datetime(df['fecha_scraping'], errors='coerce')
        df = df.sort_values(by='fecha_scraping', ascending=False).reset_index(drop=True)
    
    # Métricas principales
    col1, col2, col3 = st.columns(3)
    col1.metric("📈 Total Ofertas", len(df))
    
    if 'plataforma_origen' in df.columns:
        col2.metric("🌐 Plataformas", df['plataforma_origen'].nunique())
    else:
        col2.metric("🌐 Plataformas", "N/A")
    
    if 'fecha_scraping' in df.columns and not pd.isna(df['fecha_scraping'].max()):
        col3.metric("🕒 Última Actualización", df['fecha_scraping'].max().strftime('%d/%m %H:%M'))
    else:
        col3.metric("🕒 Última Actualización", "N/A")
    
    st.markdown("---")
    
    # FILTROS MEJORADOS
    st.subheader("🔍 Filtros")
    
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        if 'plataforma_origen' in df.columns:
            plataformas = st.multiselect(
                "Plataforma", 
                options=df['plataforma_origen'].unique(), 
                default=df['plataforma_origen'].unique()
            )
        else:
            plataformas = []
    
    with col_f2:
        if 'departamento' in df.columns:
            departamentos = st.multiselect(
                "Departamento", 
                options=df['departamento'].unique(), 
                default=df['departamento'].unique()
            )
        else:
            departamentos = []
    
    # BARRA DE BÚSQUEDA EN TÍTULOS (Reemplaza las categorías fijas)
    st.subheader("🔎 Buscar por Título de Puesto")
    busqueda_titulo = st.text_input(
        "Escribe palabras clave del puesto que buscas:",
        placeholder="Ej: marketing, datos, analista, desarrollador...",
        help="Busca en todos los títulos de puesto. Separa con comas para buscar múltiples términos."
    )
    
    # Aplicar filtros
    df_filtrado = df.copy()
    
    if 'plataforma_origen' in df.columns and plataformas:
        df_filtrado = df_filtrado[df_filtrado['plataforma_origen'].isin(plataformas)]
    
    if 'departamento' in df.columns and departamentos:
        df_filtrado = df_filtrado[df_filtrado['departamento'].isin(departamentos)]
    
    # Filtrar por búsqueda en títulos (lógica OR para múltiples términos)
    if busqueda_titulo and 'titulo_puesto' in df.columns:
        terminos = [t.strip().lower() for t in busqueda_titulo.split(',')]
        mask = pd.Series(False, index=df_filtrado.index)
        for termino in terminos:
            mask = mask | df_filtrado['titulo_puesto'].str.lower().str.contains(termino, na=False)
        df_filtrado = df_filtrado[mask]
    
    # Mostrar tabla
    st.subheader(f"📋 Listado de Ofertas ({len(df_filtrado)} resultados)")
    
    columnas_mostrar = ['fecha_scraping', 'plataforma_origen', 'titulo_puesto', 'empresa', 'departamento', 'modalidad', 'link_oferta']
    columnas_existentes = [col for col in columnas_mostrar if col in df_filtrado.columns]
    
    if columnas_existentes:
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
    st.info("📭 No hay datos disponibles. Ejecuta el pipeline desde GitHub Actions primero.")

# Footer
st.markdown("---")
st.caption("Proyecto de Pasantía | Pipeline de Extracción de Ofertas Laborales con IA | Desplegado en Streamlit Community Cloud")
