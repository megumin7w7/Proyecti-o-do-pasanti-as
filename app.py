"""
Módulo: app.py (Dashboard Visual Estable)
- Config de búsquedas: Google Sheets (Config_Busquedas)
- Resultados: artifact Excel de GitHub Actions
- Descarga: Excel generado al vuelo en Streamlit
Desplegado en: Streamlit Community Cloud
"""
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import requests
import json
import io
import zipfile
from datetime import datetime

st.set_page_config(page_title="Laboral AI Dashboard", page_icon="📊", layout="wide")

st.title("📊 Dashboard de Ofertas Laborales")
st.markdown(
    "Pipeline automatizado: GitHub Actions scrapea y genera el Excel; "
    "este dashboard configura búsquedas y permite descargar los resultados."
)

REPO_OWNER = "megumin7w7"
REPO_NAME = "Proyecti-o-do-pasanti-as"
ARTIFACT_NAME = "ofertas-excel"
WORKFLOW_FILE = "scraper.yml"  # nombre del archivo en .github/workflows/


# ==============================================================================
# 1. AUTENTICACIÓN GOOGLE SHEETS (solo config de búsquedas)
# ==============================================================================
@st.cache_resource
def get_sheets_client():
    try:
        creds_json = st.secrets.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            return None
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.sidebar.error(f"Error de autenticación: {e}")
        return None


def _github_headers():
    token = st.secrets.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


# ==============================================================================
# 2. SIDEBAR: BÚSQUEDAS + DISPARO DE ACTIONS
# ==============================================================================
st.sidebar.header("⚙️ Control del Pipeline")

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

                    config_sheet.append_row([nuevo_puesto.strip(), nuevo_lugar.strip(), "SI", "-"])
                    st.success(f"✅ Búsqueda agregada: '{nuevo_puesto}' en '{nuevo_lugar}'")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al agregar: {e}")
            else:
                st.error("No hay conexión a Google Sheets.")

with st.sidebar.expander("📋 Búsquedas Activas", expanded=True):
    client = get_sheets_client()
    if client:
        try:
            sheet = client.open("Laboral_AI_Scraper_Data")
            try:
                config_sheet = sheet.worksheet("Config_Busquedas")
                busquedas_data = config_sheet.get_all_records()

                if busquedas_data:
                    busquedas_df = pd.DataFrame(busquedas_data)
                    if "Puesto" in busquedas_df.columns:
                        activas = busquedas_df[
                            busquedas_df["Activo"].astype(str).str.upper().str.strip() == "SI"
                        ]
                        if activas.empty:
                            st.info("No hay búsquedas activas configuradas.")
                        else:
                            for idx, row in busquedas_df.iterrows():
                                if str(row.get("Activo", "")).strip().upper() == "SI":
                                    col_a, col_b = st.columns([4, 1])
                                    with col_a:
                                        st.text(f"📍 {row['Puesto']} - {row['Lugar']}")
                                    with col_b:
                                        if st.button("🗑️", key=f"del_{idx}"):
                                            try:
                                                fila_sheet = idx + 2
                                                config_sheet.update_cell(fila_sheet, 3, "NO")
                                                st.success("✅ Eliminada")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Error al eliminar: {e}")
                    else:
                        st.info("No hay columnas válidas configuradas aún.")
                else:
                    st.info("No hay búsquedas configuradas aún.")
            except gspread.WorksheetNotFound:
                st.info("No hay pestaña 'Config_Busquedas'. Agrega una búsqueda para crearla.")
        except Exception as e:
            st.sidebar.error(f"Error cargando búsquedas: {e}")
    else:
        st.sidebar.error("No se pudo conectar a Google Sheets. Verifica tus secretos.")

if st.sidebar.button("🚀 Ejecutar Scraping en Segundo Plano", type="primary", use_container_width=True):
    with st.spinner("Enviando orden a GitHub Actions..."):
        github_token = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN"))
        if not github_token:
            st.error("❌ Falta GITHUB_TOKEN en secrets de Streamlit.")
        else:
            url = (
                f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
                f"/actions/workflows/{WORKFLOW_FILE}/dispatches"
            )
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            response = requests.post(url, headers=headers, json={"ref": "main"}, timeout=30)

            if response.status_code == 204:
                st.success("✅ ¡Orden enviada! Cuando termine el workflow, pulsa Actualizar resultados.")
            else:
                st.error(f"❌ Error: {response.status_code} - {response.text}")

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 Las búsquedas viven en Google Sheets (Config_Busquedas). "
    "Los resultados salen del Excel de la última corrida de Actions."
)


# ==============================================================================
# 3. CARGA DESDE ARTIFACT DE GITHUB ACTIONS
# ==============================================================================
@st.cache_data(ttl=120)
def cargar_ofertas_desde_artifact():
    """
    Descarga el artifact 'ofertas-excel' de la última run exitosa
    y devuelve (DataFrame, bytes_xlsx_original | None).
    """
    headers = _github_headers()
    if not headers:
        return pd.DataFrame(), None, "Falta GITHUB_TOKEN en secrets."

    try:
        runs_url = (
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs"
            f"?status=success&per_page=15"
        )
        r = requests.get(runs_url, headers=headers, timeout=30)
        r.raise_for_status()
        runs = r.json().get("workflow_runs", [])
        if not runs:
            return pd.DataFrame(), None, "No hay workflow runs exitosos todavía."

        run_id = None
        for run in runs:
            path = (run.get("path") or "").lower()
            name = (run.get("name") or "").lower()
            if "scraper" in path or "scraper" in name or "scraping" in name:
                run_id = run["id"]
                break
        if run_id is None:
            run_id = runs[0]["id"]

        art_url = (
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
            f"/actions/runs/{run_id}/artifacts"
        )
        r = requests.get(art_url, headers=headers, timeout=30)
        r.raise_for_status()
        artifacts = r.json().get("artifacts", [])
        art = next(
            (a for a in artifacts if a.get("name") == ARTIFACT_NAME and not a.get("expired")),
            None,
        )
        if not art:
            return (
                pd.DataFrame(),
                None,
                f"No se encontró artifact '{ARTIFACT_NAME}' en la run {run_id}. "
                "¿Ya corrió el pipeline con el paso de upload-artifact?",
            )

        dl = requests.get(art["archive_download_url"], headers=headers, timeout=120)
        dl.raise_for_status()

        xlsx_bytes = None
        with zipfile.ZipFile(io.BytesIO(dl.content)) as zf:
            names = zf.namelist()
            target = next((n for n in names if n.endswith("ofertas_latest.xlsx")), None)
            if not target:
                target = next((n for n in names if n.lower().endswith(".xlsx")), None)
            if target:
                xlsx_bytes = zf.read(target)

        if not xlsx_bytes:
            return pd.DataFrame(), None, "El artifact no contenía un archivo .xlsx."

        df = pd.read_excel(io.BytesIO(xlsx_bytes), engine="openpyxl")
        return df, xlsx_bytes, None

    except Exception as e:
        return pd.DataFrame(), None, str(e)


# ==============================================================================
# 4. VISUALIZACIÓN + DESCARGA EXCEL
# ==============================================================================
col_btn1, col_btn2 = st.columns([1, 3])
with col_btn1:
    if st.button("🔄 Actualizar resultados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

df, xlsx_raw, error_carga = cargar_ofertas_desde_artifact()

if error_carga and df.empty:
    st.warning(f"⚠️ {error_carga}")
    st.info(
        "Asegúrate de haber ejecutado el scraping al menos una vez y de que el workflow "
        "suba el artifact `ofertas-excel`."
    )
elif df.empty:
    st.info("📭 No hay datos en el último artifact. Ejecuta el pipeline y espera a que termine.")
else:
    if "fecha_scraping" in df.columns:
        df["fecha_scraping"] = pd.to_datetime(df["fecha_scraping"], errors="coerce")
        df = df.sort_values(by="fecha_scraping", ascending=False).reset_index(drop=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("📈 Total Ofertas", len(df))
    if "plataforma_origen" in df.columns:
        col2.metric("🌐 Plataformas", df["plataforma_origen"].nunique())
    else:
        col2.metric("🌐 Plataformas", "N/A")
    if "fecha_scraping" in df.columns and df["fecha_scraping"].notna().any():
        col3.metric("🕒 Última fecha en datos", df["fecha_scraping"].max().strftime("%d/%m %H:%M"))
    else:
        col3.metric("🕒 Última fecha en datos", "N/A")

    st.markdown("---")
    st.subheader("🔍 Filtros")
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        if "plataforma_origen" in df.columns:
            plataformas = st.multiselect(
                "Plataforma",
                options=list(df["plataforma_origen"].dropna().unique()),
                default=list(df["plataforma_origen"].dropna().unique()),
            )
        else:
            plataformas = []

    with col_f2:
        if "departamento" in df.columns:
            departamentos = st.multiselect(
                "Departamento",
                options=list(df["departamento"].dropna().unique()),
                default=list(df["departamento"].dropna().unique()),
            )
        else:
            departamentos = []

    st.subheader("🔎 Buscar por Título de Puesto")
    busqueda_titulo = st.text_input(
        "Escribe palabras clave del puesto que buscas:",
        placeholder="Ej: marketing, datos, analista, desarrollador...",
        help="Separa con comas para varios términos (OR).",
    )

    df_filtrado = df.copy()
    if "plataforma_origen" in df_filtrado.columns and plataformas:
        df_filtrado = df_filtrado[df_filtrado["plataforma_origen"].isin(plataformas)]
    if "departamento" in df_filtrado.columns and departamentos:
        df_filtrado = df_filtrado[df_filtrado["departamento"].isin(departamentos)]
    if busqueda_titulo and "titulo_puesto" in df_filtrado.columns:
        terminos = [t.strip().lower() for t in busqueda_titulo.split(",") if t.strip()]
        mask = pd.Series(False, index=df_filtrado.index)
        for termino in terminos:
            mask = mask | df_filtrado["titulo_puesto"].astype(str).str.lower().str.contains(
                termino, na=False
            )
        df_filtrado = df_filtrado[mask]

    st.subheader(f"📋 Listado de Ofertas ({len(df_filtrado)} resultados)")

    columnas_mostrar = [
        "fecha_scraping",
        "plataforma_origen",
        "titulo_puesto",
        "empresa",
        "departamento",
        "modalidad",
        "link_oferta",
    ]
    columnas_existentes = [c for c in columnas_mostrar if c in df_filtrado.columns]

    if columnas_existentes:
        st.dataframe(
            df_filtrado[columnas_existentes],
            use_container_width=True,
            hide_index=True,
            column_config={
                "link_oferta": st.column_config.LinkColumn("Ver Oferta", display_text="🔗 Abrir")
            }
            if "link_oferta" in columnas_existentes
            else None,
        )
    else:
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

    st.markdown("### 📥 Descargas")
    c1, c2 = st.columns(2)

    # Excel filtrado generado al vuelo
    buf = io.BytesIO()
    df_filtrado.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    with c1:
        st.download_button(
            label="📥 Excel (vista filtrada)",
            data=buf.getvalue(),
            file_name=f"ofertas_filtradas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # Excel completo de la última corrida (bytes del artifact)
    with c2:
        if xlsx_raw:
            st.download_button(
                label="📥 Excel completo (última corrida)",
                data=xlsx_raw,
                file_name="ofertas_latest.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.caption("Excel completo del artifact no disponible.")

st.markdown("---")
st.caption(
    "Proyecto de Pasantía | Pipeline de Extracción de Ofertas Laborales con IA | "
    "Streamlit Community Cloud + GitHub Actions artifacts"
)
