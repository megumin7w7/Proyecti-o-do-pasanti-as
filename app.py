"""
Módulo: app.py (Dashboard Visual Estable)
- Config de búsquedas: Google Sheets (Config_Busquedas)
- Resultados: artifact Excel de GitHub Actions
- Descarga: Excel generado al vuelo en Streamlit
- Feedback visual: pantalla de carga + video en esquina + polling de estado
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
import time
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
WORKFLOW_FILE = "scraper.yml"

# ================================================================
# VIDEO DE CARGA — CAMBIA ESTA URL POR LA DE TU VIDEO
# ================================================================
CORNER_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


# ==============================================================================
# 1. AUTENTICACIÓN GOOGLE SHEETS
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
# 2. FUNCIONES DE ESTADO DEL WORKFLOW
# ==============================================================================
def get_latest_workflow_run(headers, status_filter=None):
    """Obtiene la última run del workflow scraper."""
    try:
        url = (
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs"
            f"?per_page=10"
        )
        if status_filter:
            url += f"&status={status_filter}"
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        runs = r.json().get("workflow_runs", [])
        for run in runs:
            path = (run.get("path") or "").lower()
            name = (run.get("name") or "").lower()
            if "scraper" in path or "scraper" in name or "scraping" in name:
                return run
        return None
    except Exception:
        return None


def get_workflow_status_display(run):
    """Convierte estado de run en texto + emoji."""
    if not run:
        return "❓ Desconocido", "unknown"
    status = run.get("status", "unknown")
    conclusion = run.get("conclusion", "")
    if status == "queued":
        return "⏳ En cola...", "queued"
    elif status == "in_progress":
        return "🔄 Ejecutando scraping...", "running"
    elif status == "completed":
        if conclusion == "success":
            return "✅ Completado exitosamente", "success"
        elif conclusion == "failure":
            return "❌ Falló la ejecución", "failed"
        elif conclusion == "cancelled":
            return "🚫 Cancelado", "cancelled"
        else:
            return f"⚠️ Completado: {conclusion}", "other"
    else:
        return f"📌 Estado: {status}", "other"


# ==============================================================================
# 3. VIDEO EN ESQUINA INFERIOR DERECHA
# ==============================================================================
def show_corner_video(video_url):
    """Muestra video pequeño fijo en esquina inferior derecha."""
    is_youtube = "youtube.com" in video_url or "youtu.be" in video_url

    if is_youtube:
        if "youtu.be" in video_url:
            yt_id = video_url.split("/")[-1].split("?")[0]
        else:
            yt_id = video_url.split("v=")[-1].split("&")[0]
        video_html = f"""
        <iframe
            src="https://www.youtube.com/embed/{yt_id}?autoplay=1&mute=1&loop=1&playlist={yt_id}&controls=0"
            style="width:100%;height:100%;border:none;border-radius:12px;"
            allow="autoplay; muted"
        ></iframe>
        """
    else:
        video_html = f"""
        <video autoplay muted loop playsinline
            style="width:100%;height:100%;object-fit:cover;border-radius:12px;">
            <source src="{video_url}" type="video/mp4">
        </video>
        """

    st.markdown(
        f"""
        <style>
            #corner-video-container {{
                position: fixed;
                bottom: 24px;
                right: 24px;
                width: 260px;
                height: 180px;
                z-index: 9999;
                border-radius: 14px;
                overflow: hidden;
                box-shadow: 0 8px 32px rgba(0,0,0,0.5);
                border: 2px solid rgba(255,255,255,0.15);
                background: #000;
                animation: slideIn 0.4s ease-out;
            }}
            #corner-video-container::before {{
                content: "⏳ Pipeline en progreso";
                position: absolute;
                top: -28px;
                left: 0;
                right: 0;
                text-align: center;
                font-size: 11px;
                font-weight: 600;
                color: #22D3EE;
                letter-spacing: 0.05em;
            }}
            @keyframes slideIn {{
                from {{ opacity: 0; transform: translateY(20px) scale(0.95); }}
                to {{ opacity: 1; transform: translateY(0) scale(1); }}
            }}
        </style>
        <div id="corner-video-container">
            {video_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def hide_corner_video():
    """Oculta el video de la esquina."""
    st.markdown(
        """<style>#corner-video-container{display:none !important;}</style>""",
        unsafe_allow_html=True
    )


# ==============================================================================
# 4. SIDEBAR: BÚSQUEDAS + DISPARO DE ACTIONS CON FEEDBACK
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

# --- Verificar estado actual del workflow ---
headers = _github_headers()
workflow_is_running = False
workflow_status_text = ""
workflow_run_url = ""

if headers:
    latest_run = get_latest_workflow_run(headers)
    if latest_run:
        status_display, status_key = get_workflow_status_display(latest_run)
        workflow_status_text = status_display
        workflow_run_url = latest_run.get("html_url", "")
        if status_key in ("queued", "running"):
            workflow_is_running = True

# --- Mostrar estado actual del workflow en sidebar ---
if workflow_status_text:
    if workflow_is_running:
        st.sidebar.warning(f"**{workflow_status_text}**")
        if workflow_run_url:
            st.sidebar.markdown(f"[👀 Ver progreso en GitHub]({workflow_run_url})")
    elif "exitosamente" in workflow_status_text:
        st.sidebar.success(f"**{workflow_status_text}**")
    elif "Falló" in workflow_status_text:
        st.sidebar.error(f"**{workflow_status_text}**")
    else:
        st.sidebar.info(f"**{workflow_status_text}**")

# --- Botón de ejecutar con feedback completo ---
if workflow_is_running:
    st.sidebar.button(
        "🚀 Scraping en progreso...",
        type="primary",
        use_container_width=True,
        disabled=True,
    )
    st.sidebar.caption("⏳ Espera a que termine el workflow actual.")
    show_corner_video(CORNER_VIDEO_URL)
else:
    if st.sidebar.button(
        "🚀 Ejecutar Scraping en Segundo Plano",
        type="primary",
        use_container_width=True,
    ):
        show_corner_video(CORNER_VIDEO_URL)

        placeholder = st.sidebar.empty()

        with placeholder.container():
            st.markdown("### 🔄 Iniciando pipeline...")
            progress_bar = st.progress(0, text="Enviando orden a GitHub Actions...")

            github_token = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN"))
            if not github_token:
                progress_bar.empty()
                hide_corner_video()
                st.error("❌ Falta GITHUB_TOKEN en secrets de Streamlit.")
            else:
                url = (
                    f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
                    f"/actions/workflows/{WORKFLOW_FILE}/dispatches"
                )
                gh_headers = {
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }

                try:
                    response = requests.post(url, headers=gh_headers, json={"ref": "main"}, timeout=30)
                except Exception as e:
                    progress_bar.empty()
                    hide_corner_video()
                    st.error(f"❌ Error de conexión: {e}")
                    response = None

                if response and response.status_code == 204:
                    progress_bar.progress(20, text="✅ Orden enviada. Buscando workflow...")
                    time.sleep(3)

                    progress_bar.progress(40, text="🔍 Detectando ejecución...")
                    new_run = None
                    for attempt in range(6):
                        new_run = get_latest_workflow_run(gh_headers)
                        if new_run and new_run.get("status") in ("queued", "in_progress"):
                            break
                        time.sleep(2)

                    if new_run:
                        run_url = new_run.get("html_url", "")
                        progress_bar.progress(50, text="⏳ Workflow encontrado. Monitoreando...")

                        status_placeholder = st.empty()
                        step_names = [
                            "Clonando repositorio...",
                            "Instalando dependencias...",
                            "Ejecutando scrapers...",
                            "Procesando con NLP...",
                            "Subiendo resultados...",
                        ]

                        for poll in range(30):
                            run_check = get_latest_workflow_run(gh_headers)
                            if run_check:
                                s = run_check.get("status", "")
                                c = run_check.get("conclusion", "")

                                if s == "completed":
                                    if c == "success":
                                        progress_bar.progress(100, text="✅ ¡Scraping completado!")
                                        status_placeholder.success("🎉 Resultados disponibles en 1-2 minutos.")
                                    else:
                                        progress_bar.progress(100, text=f"⚠️ Workflow: {c}")
                                        status_placeholder.warning(f"Estado: {c}")
                                    hide_corner_video()
                                    break

                                elif s == "in_progress":
                                    estimated_progress = 55 + min(poll * 1.5, 40)
                                    step_idx = min(int(poll / 6), len(step_names) - 1)
                                    progress_bar.progress(
                                        int(estimated_progress),
                                        text=f"🔄 {step_names[step_idx]}"
                                    )
                                    status_placeholder.info(f"⏱️ Monitoreando... (intento {poll + 1}/30)")

                                elif s == "queued":
                                    progress_bar.progress(50, text="⏳ En cola...")
                                    status_placeholder.info("Esperando runner...")

                                time.sleep(3)
                        else:
                            progress_bar.progress(85, text="⏱️ Timeout, workflow sigue corriendo.")
                            if run_url:
                                st.info(f"📍 [Ver progreso en GitHub]({run_url})")
                            st.caption("Vuelve en unos minutos y pulsa 'Actualizar resultados'.")

                    else:
                        progress_bar.progress(60, text="⚠️ Run no detectada, orden enviada.")
                        st.info("Pulsa 'Actualizar resultados' cuando termine.")

                elif response:
                    progress_bar.empty()
                    hide_corner_video()
                    st.error(f"❌ Error: {response.status_code} - {response.text}")

                time.sleep(2)
                placeholder.empty()
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 Las búsquedas viven en Google Sheets (Config_Busquedas). "
    "Los resultados salen del Excel de la última corrida de Actions."
)


# ==============================================================================
# 5. CARGA DESDE ARTIFACT DE GITHUB ACTIONS
# ==============================================================================
@st.cache_data(ttl=120)
def cargar_ofertas_desde_artifact():
    """Descarga el artifact 'ofertas-excel' de la última run exitosa."""
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
# 6. VISUALIZACIÓN + DESCARGA EXCEL
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
