"""
Panel de estación — Nivel de ríos/quebradas (CORNARE / MARCO)
--------------------------------------------------------------------
Fijada a la estación 23 (José Daniel Restrepo Ramírez). El código de
estación no es editable: vive en CODIGO_ESTACION.

Para correrla (recuerda mantener la carpeta .streamlit/ junto a este
archivo para que cargue el tema claro):
    streamlit run app_nivel_cornare.py

Requiere: streamlit>=1.25, pandas, numpy, requests, plotly, pydeck, openpyxl.

Nota sobre ubicación, fotos y metadatos:
El endpoint de "nivel" solo trae fecha/valor, no metadatos de la
estación. Por eso esta app también consulta el LISTADO de estaciones
(que sí trae nombre, coordenadas, corriente, municipio y -si existen-
fotos) y busca ahí la estación 23. No conozco de antemano los nombres
exactos de esas llaves en la API real, así que se prueban varios
nombres comunes (ver CANDIDATOS_* más abajo). Si el mapa, el título,
las fotos o el contexto no salen bien, abre "Datos crudos de la
estación" para ver las llaves reales y ajústalas ahí.
"""

import io
import requests
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import pydeck as pdk
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------------------------
# Estación fija de esta app
# ------------------------------------------------------------------
CODIGO_ESTACION = "23"

# Coordenadas por defecto (Institución Universitaria Pascual Bravo) —
# se usan solo si no logramos encontrar la ubicación real.
LAT_DEFECTO = 6.2766
LON_DEFECTO = -75.5901

API_BASE_URL = "https://marco.cornare.gov.co/api/v1/estaciones"
LLAVE_FECHA = "level_date"
LLAVE_VALOR = "level"

ENDPOINTS_INFO_ESTACION = ["{base}/{codigo}/", "{base}/{codigo}", "{base}/"]

CANDIDATOS_ID = ["id", "codigo", "code", "station_id", "id_estacion"]
CANDIDATOS_LAT = ["lat", "latitude", "latitud"]
CANDIDATOS_LON = ["lng", "lon", "long", "longitude", "longitud"]
CANDIDATOS_NOMBRE = ["nombre", "name", "station_name", "nombre_estacion"]
CANDIDATOS_CORRIENTE = ["corriente", "stream", "rio", "quebrada", "water_body", "cuerpo_agua"]
CANDIDATOS_MUNICIPIO = ["municipio", "town", "city", "municipality"]
CANDIDATOS_TIPO = ["tipo", "type", "station_type", "tipo_estacion"]
CANDIDATOS_ALTITUD = ["altitud", "elevation", "alt", "altitude"]
CANDIDATOS_CUENCA = ["cuenca", "basin", "subcuenca"]
CANDIDATOS_FOTOS = [
    "foto", "fotos", "imagen", "imagenes", "photo", "photos",
    "image", "images", "picture", "pictures", "url_foto", "foto_url",
    "imagen_url", "photo_url",
]

# ------------------------------------------------------------------
# Paleta y tipografía — tema claro, inspirado en el geoportal MARCO
# ------------------------------------------------------------------
BG = "#F5F7F6"
PANEL = "#FFFFFF"
LINE = "#E2E8E6"
TEXT = "#182722"
MUTED = "#5C726C"
ACCENT = "#1F7A4D"        # verde Cornare — marca, botones, cifras
ACCENT_SOFT = "#E9F4EE"   # fondo suave para insignias
ACCENT_WARM = "#C2703A"   # alertas / outliers / crecidas
MAP_ACCENT = "#57C3D3"    # marcador sobre el mapa oscuro (sin cambios)
SHADOW = "0 2px 14px rgba(24, 39, 34, 0.07)"

st.set_page_config(page_title="Estación 23 — MARCO Cornare", page_icon="🌊", layout="wide")

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}
    .stApp {{ background: {BG}; }}
    .block-container {{ padding-top: 4rem; max-width: 1180px; }}

    /* ---------- topbar de marca ---------- */
    .topbar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: {PANEL};
        border: 1px solid {LINE};
        border-radius: 16px;
        box-shadow: {SHADOW};
        padding: 14px 22px;
        margin-bottom: 30px;
    }}
    .topbar-left {{ display: flex; align-items: center; gap: 14px; }}
    .brand-mark {{
        width: 40px; height: 40px;
        border-radius: 50%;
        background: {ACCENT};
        color: white;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.15rem;
    }}
    .brand-name {{ font-weight: 700; color: {TEXT}; font-size: 1.05rem; line-height: 1.2; }}
    .brand-sub {{ color: {MUTED}; font-size: 0.82rem; }}
    .topbar-badge {{
        background: {ACCENT_SOFT};
        color: {ACCENT};
        font-weight: 600;
        font-size: 0.85rem;
        padding: 7px 16px;
        border-radius: 999px;
    }}

    /* ---------- encabezado de estación ---------- */
    .panel-hero {{ padding: 0 4px 24px 4px; }}
    .panel-hero h1 {{
        font-family: 'Fraunces', serif;
        font-weight: 600;
        font-size: 2.5rem;
        line-height: 1.15;
        color: {TEXT};
        margin: 0 0 8px 0;
    }}
    .panel-hero p {{
        color: {MUTED};
        font-size: 0.98rem;
        margin: 0 0 16px 0;
        max-width: 62ch;
    }}
    .meta-row {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .meta-pill {{
        background: {PANEL};
        border: 1px solid {LINE};
        color: {MUTED};
        font-size: 0.82rem;
        padding: 5px 13px;
        border-radius: 999px;
    }}
    .meta-pill b {{ color: {TEXT}; font-weight: 600; }}

    /* ---------- franja de lecturas ---------- */
    .readout-strip {{ display: flex; flex-wrap: wrap; gap: 14px; margin: 0 0 24px 0; }}
    .readout {{
        flex: 1 1 170px;
        background: {PANEL};
        border: 1px solid {LINE};
        border-left: 3px solid {ACCENT};
        border-radius: 12px;
        box-shadow: {SHADOW};
        padding: 16px 20px;
    }}
    .readout.warm {{ border-left-color: {ACCENT_WARM}; }}
    .readout-label {{ color: {MUTED}; font-size: 0.8rem; margin-bottom: 6px; }}
    .readout-value {{
        color: {TEXT};
        font-size: 1.8rem;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.01em;
    }}
    .readout-value.warm {{ color: {ACCENT_WARM}; }}
    .readout-sub {{ color: {MUTED}; font-size: 0.78rem; margin-top: 4px; }}
    .readout-sub.up {{ color: {ACCENT_WARM}; }}
    .readout-sub.down {{ color: {ACCENT}; }}

    /* ---------- notas y detalle de coordenadas ---------- */
    .panel-note {{ color: {MUTED}; font-size: 0.88rem; margin-bottom: 14px; }}
    .coord-readout {{
        font-variant-numeric: tabular-nums;
        color: {MUTED};
        font-size: 0.85rem;
        padding-top: 12px;
    }}
    .coord-readout span {{ color: {ACCENT}; font-weight: 600; }}

    /* ---------- tira de fotos ---------- */
    .filmstrip {{ display: flex; gap: 12px; overflow-x: auto; padding-bottom: 4px; }}
    .filmstrip img {{
        height: 210px; width: auto;
        object-fit: cover;
        border-radius: 10px;
        border: 1px solid {LINE};
        flex-shrink: 0;
    }}

    /* ---------- eventos de crecida ---------- */
    .evento-fila {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 12px;
        padding: 11px 0;
        border-bottom: 1px solid {LINE};
        font-size: 0.9rem;
    }}
    .evento-fila:last-child {{ border-bottom: none; }}
    .evento-fecha {{ color: {MUTED}; }}
    .evento-pico {{ color: {ACCENT_WARM}; font-weight: 600; font-variant-numeric: tabular-nums; }}

    /* ---------- paneles con borde (st.container(border=True)) ---------- */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: {PANEL};
        border: 1px solid {LINE} !important;
        border-radius: 16px !important;
        box-shadow: {SHADOW};
    }}
    [data-testid="stVerticalBlockBorderWrapper"] h3 {{
        font-weight: 600;
        font-size: 1.02rem;
        color: {TEXT};
        margin: 0 0 4px 0;
    }}
    .control-label {{ color: {MUTED}; font-size: 0.8rem; margin-bottom: 10px; }}
    [data-testid="stWidgetLabel"] p {{ color: {TEXT} !important; }}

    /* ---------- widgets nativos ---------- */
    [data-testid="stButton"] button, [data-testid="stDownloadButton"] button {{
        background: {ACCENT};
        color: white;
        border: none;
        border-radius: 999px;
        font-weight: 600;
        padding: 0.5rem 1.1rem;
    }}
    [data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover {{
        background: #17603C;
        color: white;
    }}
    [data-testid="stExpander"] {{
        border: 1px solid {LINE};
        border-radius: 14px;
        background: {PANEL};
    }}
    /* Fuerza texto e ícono oscuros en el encabezado del expander — si el tema
       activo en Streamlit Cloud no coincide con nuestro config.toml (por ejemplo,
       si alguien fijó un tema manual en la configuración de la app), el texto por
       defecto queda claro sobre nuestro fondo blanco y se vuelve invisible. */
    [data-testid="stExpander"] summary {{ color: {TEXT} !important; }}
    [data-testid="stExpander"] summary p {{ color: {TEXT} !important; }}
    [data-testid="stExpander"] summary svg {{ fill: {TEXT} !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# Funciones de consulta — serie de nivel
# ------------------------------------------------------------------
def obtener_serie_nivel(codigo_estacion, desde, hasta, calidad=1, timeout=30):
    url = f"{API_BASE_URL}/{codigo_estacion}/nivel"
    params = {"desde": desde, "hasta": hasta, "calidad": calidad}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout, verify=False)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"HTTP {resp.status_code}"
    except requests.exceptions.RequestException as e:
        return None, f"Error de red: {e}"


def obtener_todas_las_paginas(datos_json, timeout=30):
    registros = list(datos_json.get("values", []))
    siguiente_url = datos_json.get("next")
    while siguiente_url:
        try:
            resp = requests.get(siguiente_url, timeout=timeout, verify=False)
        except requests.exceptions.RequestException:
            break
        if resp.status_code != 200:
            break
        pagina = resp.json()
        registros.extend(pagina.get("values", []))
        siguiente_url = pagina.get("next")
    return registros


# ------------------------------------------------------------------
# Funciones de consulta — metadatos de la estación
# ------------------------------------------------------------------
def _valor_por_candidatos(d, candidatos):
    if not isinstance(d, dict):
        return None
    for k in candidatos:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _buscar_estacion_en_lista(lista, codigo_estacion):
    if not isinstance(lista, list):
        return None
    codigo_str = str(codigo_estacion).strip()
    for item in lista:
        if not isinstance(item, dict):
            continue
        candidato_id = _valor_por_candidatos(item, CANDIDATOS_ID)
        if candidato_id is not None and str(candidato_id).strip() == codigo_str:
            return item
    return None


@st.cache_data(show_spinner=False, ttl=3600)
def obtener_info_estacion(codigo_estacion, timeout=20):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    for plantilla in ENDPOINTS_INFO_ESTACION:
        url = plantilla.format(base=API_BASE_URL, codigo=codigo_estacion)
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, verify=False)
        except requests.exceptions.RequestException:
            continue
        if resp.status_code != 200:
            continue
        try:
            data = resp.json()
        except ValueError:
            continue

        if isinstance(data, dict) and _valor_por_candidatos(data, CANDIDATOS_LAT) is not None:
            return data, url

        lista = data.get("values") if isinstance(data, dict) else data
        if isinstance(data, dict) and lista is None:
            for k in ("results", "estaciones", "data"):
                if isinstance(data.get(k), list):
                    lista = data[k]
                    break
        if isinstance(lista, list):
            encontrada = _buscar_estacion_en_lista(lista, codigo_estacion)
            if encontrada:
                return encontrada, url

    return None, None


def detectar_coordenadas(info_estacion):
    lat = _valor_por_candidatos(info_estacion, CANDIDATOS_LAT)
    lon = _valor_por_candidatos(info_estacion, CANDIDATOS_LON)
    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon), True
        except (TypeError, ValueError):
            pass
    return LAT_DEFECTO, LON_DEFECTO, False


def detectar_fotos(info_estacion):
    if not isinstance(info_estacion, dict):
        return []
    valor = _valor_por_candidatos(info_estacion, CANDIDATOS_FOTOS)
    if valor is None:
        return []

    urls = []
    if isinstance(valor, str):
        urls.append(valor)
    elif isinstance(valor, list):
        for elem in valor:
            if isinstance(elem, str):
                urls.append(elem)
            elif isinstance(elem, dict):
                sub_url = _valor_por_candidatos(elem, ["url", "foto", "imagen", "image", "photo", "src", "link"])
                if sub_url:
                    urls.append(sub_url)

    vistos, urls_limpias = set(), []
    for u in urls:
        if u and u not in vistos:
            vistos.add(u)
            urls_limpias.append(u)
    return urls_limpias


def construir_pills_contexto(info_estacion):
    """Arma insignias de contexto (corriente, municipio, cuenca, tipo, altitud) con lo que
    realmente exista en los metadatos de la API. Las que no se encuentren simplemente no se muestran."""
    campos = [
        ("Corriente", _valor_por_candidatos(info_estacion, CANDIDATOS_CORRIENTE)),
        ("Municipio", _valor_por_candidatos(info_estacion, CANDIDATOS_MUNICIPIO)),
        ("Cuenca", _valor_por_candidatos(info_estacion, CANDIDATOS_CUENCA)),
        ("Tipo", _valor_por_candidatos(info_estacion, CANDIDATOS_TIPO)),
        ("Altitud", _valor_por_candidatos(info_estacion, CANDIDATOS_ALTITUD)),
    ]
    pills = []
    for etiqueta, valor in campos:
        if valor is not None and str(valor).strip() != "":
            texto = f"{valor} m" if etiqueta == "Altitud" and str(valor).replace(".", "", 1).isdigit() else str(valor)
            pills.append(f'<div class="meta-pill">{etiqueta}: <b>{texto}</b></div>')
    return pills


def calcular_calidad(df):
    """Devuelve indice(0-100), huecos, n_outliers, y una máscara booleana de outliers alineada a df."""
    if df.empty or len(df) < 2:
        return 0.0, 0, 0, pd.Series(False, index=df.index)

    df_idx = df.set_index("fecha")
    frecuencia_tipica = df["fecha"].diff().dropna().mode()
    if len(frecuencia_tipica) == 0:
        return 0.0, 0, 0, pd.Series(False, index=df.index)
    frecuencia_tipica = frecuencia_tipica[0]

    rango_completo = pd.date_range(start=df_idx.index.min(), end=df_idx.index.max(), freq=frecuencia_tipica)
    esperados = len(rango_completo)
    huecos = esperados - len(df_idx)
    completitud = max(0.0, 1 - (huecos / esperados)) if esperados > 0 else 0.0

    Q1, Q3 = df["nivel"].quantile(0.25), df["nivel"].quantile(0.75)
    IQR = Q3 - Q1
    lim_inf, lim_sup = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
    es_outlier = (df["nivel"] < lim_inf) | (df["nivel"] > lim_sup) | (df["nivel"] < 0)
    proporcion_outliers = es_outlier.mean()

    indice = (completitud * 0.7 + (1 - proporcion_outliers) * 0.3) * 100
    return round(indice, 1), int(huecos), int(es_outlier.sum()), es_outlier


GAP_FUSION_EVENTOS = pd.Timedelta(hours=1)  # rachas de outliers separadas por menos de esto se fusionan en un solo evento
MAX_EVENTOS_MOSTRADOS = 12


def detectar_eventos_crecida(df, es_outlier, gap_fusion=GAP_FUSION_EVENTOS):
    """
    Agrupa outliers consecutivos en 'eventos de crecida' (inicio, fin, pico, duración).
    Cuando el nivel oscila justo alrededor del umbral de outlier, quedan muchas rachas
    diminutas separadas por minutos; para no mostrar decenas de "eventos" casi idénticos,
    se fusionan las rachas cuyo espacio entre una y la siguiente es menor a `gap_fusion`.
    """
    if not es_outlier.any():
        return pd.DataFrame(columns=["inicio", "fin", "pico", "duracion_h"])

    grupos = (es_outlier != es_outlier.shift()).cumsum()
    rachas = []
    for _, sub in df[es_outlier].groupby(grupos[es_outlier]):
        rachas.append({"inicio": sub["fecha"].min(), "fin": sub["fecha"].max(), "pico": sub["nivel"].max()})
    rachas.sort(key=lambda r: r["inicio"])

    eventos = []
    for racha in rachas:
        if eventos and (racha["inicio"] - eventos[-1]["fin"]) <= gap_fusion:
            eventos[-1]["fin"] = max(eventos[-1]["fin"], racha["fin"])
            eventos[-1]["pico"] = max(eventos[-1]["pico"], racha["pico"])
        else:
            eventos.append(dict(racha))

    for ev in eventos:
        ev["duracion_h"] = round((ev["fin"] - ev["inicio"]).total_seconds() / 3600, 1)

    return pd.DataFrame(eventos).sort_values("inicio", ascending=False).reset_index(drop=True)


def grafico_nivel(df, es_outlier):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["fecha"], y=df["nivel"],
        mode="lines", name="Nivel",
        line=dict(color=ACCENT, width=1.8),
        fill="tozeroy", fillcolor="rgba(31, 122, 77, 0.10)",
        hovertemplate="%{x|%d %b, %H:%M}<br>%{y:.2f}<extra></extra>",
    ))
    if es_outlier.any():
        fig.add_trace(go.Scatter(
            x=df.loc[es_outlier, "fecha"], y=df.loc[es_outlier, "nivel"],
            mode="markers", name="Outlier",
            marker=dict(color=ACCENT_WARM, size=6, line=dict(width=0)),
            hovertemplate="%{x|%d %b, %H:%M}<br>%{y:.2f}<extra>outlier</extra>",
        ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=MUTED, family="Inter"),
        margin=dict(l=0, r=0, t=6, b=0),
        height=340,
        showlegend=False,
        xaxis=dict(showgrid=False, linecolor=LINE, tickfont=dict(color=MUTED)),
        yaxis=dict(showgrid=True, gridcolor=LINE, zeroline=False, tickfont=dict(color=MUTED)),
        hoverlabel=dict(bgcolor=PANEL, font_color=TEXT, bordercolor=LINE),
    )
    return fig


def mapa_estacion(lat, lon, nombre):
    """Mapa sin cambios respecto a la versión anterior: estilo oscuro nativo de pydeck."""
    capa_punto = pdk.Layer(
        "ScatterplotLayer",
        data=[{"lat": lat, "lon": lon}],
        get_position="[lon, lat]",
        get_fill_color=[87, 195, 211, 220],
        get_radius=45,
        radius_min_pixels=6,
        radius_max_pixels=20,
    )
    capa_anillo = pdk.Layer(
        "ScatterplotLayer",
        data=[{"lat": lat, "lon": lon}],
        get_position="[lon, lat]",
        get_fill_color=[87, 195, 211, 40],
        get_radius=250,
    )
    vista = pdk.ViewState(latitude=lat, longitude=lon, zoom=12, pitch=0)
    return pdk.Deck(
        layers=[capa_anillo, capa_punto],
        initial_view_state=vista,
        map_style="dark",
        tooltip={"text": nombre or f"Estación {CODIGO_ESTACION}"},
    )


def exportar_excel(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="nivel")
    return buffer.getvalue()


# ------------------------------------------------------------------
# Info de la estación — se obtiene siempre, así el título y el
# contexto ya salen con datos reales aunque no se haya consultado
# ------------------------------------------------------------------
info_estacion, endpoint_usado = obtener_info_estacion(CODIGO_ESTACION)
nombre_estacion_api = _valor_por_candidatos(info_estacion, CANDIDATOS_NOMBRE)
titulo_app = nombre_estacion_api if nombre_estacion_api else f"Estación {CODIGO_ESTACION}"
pills_contexto = construir_pills_contexto(info_estacion)

# ------------------------------------------------------------------
# Topbar de marca
# ------------------------------------------------------------------
st.markdown(
    f"""
    <div class="topbar">
        <div class="topbar-left">
            <div class="brand-mark">🌊</div>
            <div>
                <div class="brand-name">MARCO</div>
                <div class="brand-sub">Monitoreo Ambiental Regional de Cornare</div>
            </div>
        </div>
        <div class="topbar-badge">Estación {CODIGO_ESTACION}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# Encabezado de la estación — contexto ampliado
# ------------------------------------------------------------------
fila_pills = f'<div class="meta-row">{"".join(pills_contexto)}</div>' if pills_contexto else ""
st.markdown(
    f"""
    <div class="panel-hero">
        <h1>{titulo_app}</h1>
        <p>Estación limnimétrica del sistema MARCO, operado por Cornare, en la cuenca de los ríos Negro y Nare.
        Mide el nivel del agua de forma automática y transmite sus lecturas para apoyar la vigilancia de crecidas
        e inundaciones en la zona.</p>
        {fila_pills}
    </div>
    """,
    unsafe_allow_html=True,
)
if not pills_contexto:
    st.markdown(
        f'<p class="panel-note" style="margin-top:-14px;">No se encontraron campos adicionales '
        f'(corriente, municipio, cuenca, tipo, altitud) en la respuesta de la API para esta estación — '
        f'revisa "Datos crudos de la estación" más abajo para confirmar los nombres reales de esos campos.</p>',
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------
# Barra de control — sin fechas predeterminadas
# ------------------------------------------------------------------
with st.container(border=True):
    st.markdown('<div class="control-label">Parámetros de consulta</div>', unsafe_allow_html=True)
    col_desde, col_hasta, col_calidad, col_boton = st.columns([1, 1, 1, 1])
    with col_desde:
        fecha_desde_val = st.date_input("Desde", value=None, format="YYYY/MM/DD")
    with col_hasta:
        fecha_hasta_val = st.date_input("Hasta", value=None, format="YYYY/MM/DD")
    with col_calidad:
        calidad = st.selectbox("Calidad", [1, 0], index=0, help="1 = solo datos validados")
    with col_boton:
        st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
        consultar = st.button("Consultar", type="primary", use_container_width=True)

st.markdown('<div style="height: 22px;"></div>', unsafe_allow_html=True)

# ------------------------------------------------------------------
# Consulta y procesamiento
# ------------------------------------------------------------------
if consultar and (fecha_desde_val is None or fecha_hasta_val is None):
    st.warning("Elige la fecha **desde** y la fecha **hasta** antes de consultar.")
elif consultar and fecha_desde_val > fecha_hasta_val:
    st.warning("La fecha **desde** no puede ser posterior a la fecha **hasta**.")
elif consultar:
    fecha_desde = fecha_desde_val.strftime("%Y-%m-%d")
    fecha_hasta = fecha_hasta_val.strftime("%Y-%m-%d")
    with st.spinner("Consultando la API..."):
        datos_crudos, error = obtener_serie_nivel(CODIGO_ESTACION, fecha_desde, fecha_hasta, calidad)

    if error:
        st.error(f"No se pudo consultar la estación: {error}")
    else:
        registros = obtener_todas_las_paginas(datos_crudos)

        if not registros:
            st.warning("No hay registros para este rango de fechas. Prueba otro rango.")
        else:
            df = pd.DataFrame(registros)
            df = df.rename(columns={LLAVE_FECHA: "fecha", LLAVE_VALOR: "nivel"})
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            if df["fecha"].dt.tz is not None:
                # Excel (openpyxl) no admite fechas con zona horaria — se quita el
                # sufijo de tz conservando la hora local ya reportada por la API.
                df["fecha"] = df["fecha"].dt.tz_localize(None)
            df["nivel"] = pd.to_numeric(df["nivel"], errors="coerce")
            df = df.dropna(subset=["fecha", "nivel"]).sort_values("fecha").reset_index(drop=True)

            lat, lon, coords_reales = detectar_coordenadas(info_estacion)
            fotos = detectar_fotos(info_estacion)
            indice_calidad, huecos, n_outliers, mascara_outliers = calcular_calidad(df)
            eventos = detectar_eventos_crecida(df, mascara_outliers)

            # --- Última lectura y tendencia ---
            ultimo = df.iloc[-1]
            penultimo = df.iloc[-2] if len(df) > 1 else ultimo
            delta = ultimo["nivel"] - penultimo["nivel"]
            if delta > 0.01:
                tendencia_txt, tendencia_clase, flecha = "subiendo", "up", "▲"
            elif delta < -0.01:
                tendencia_txt, tendencia_clase, flecha = "bajando", "down", "▼"
            else:
                tendencia_txt, tendencia_clase, flecha = "estable", "", "—"

            # --- Nivel máximo registrado ---
            idx_max = df["nivel"].idxmax()
            nivel_max = df.loc[idx_max, "nivel"]
            fecha_max = df.loc[idx_max, "fecha"]

            # --- Franja de lecturas ---
            st.markdown(
                f"""
                <div class="readout-strip">
                    <div class="readout">
                        <div class="readout-label">Última lectura</div>
                        <div class="readout-value">{ultimo['nivel']:.2f}</div>
                        <div class="readout-sub {tendencia_clase}">{flecha} {tendencia_txt} ({delta:+.2f})</div>
                    </div>
                    <div class="readout">
                        <div class="readout-label">Nivel promedio</div>
                        <div class="readout-value">{df['nivel'].mean():.2f}</div>
                    </div>
                    <div class="readout warm">
                        <div class="readout-label">Nivel máximo</div>
                        <div class="readout-value warm">{nivel_max:.2f}</div>
                        <div class="readout-sub">{fecha_max.strftime('%d %b, %H:%M')}</div>
                    </div>
                    <div class="readout">
                        <div class="readout-label">Lecturas</div>
                        <div class="readout-value">{len(df):,}</div>
                    </div>
                    <div class="readout">
                        <div class="readout-label">Índice de calidad</div>
                        <div class="readout-value">{indice_calidad}<span style="font-size:1.05rem;color:{MUTED};"> /100</span></div>
                    </div>
                    <div class="readout warm">
                        <div class="readout-label">Outliers</div>
                        <div class="readout-value warm">{n_outliers}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # --- Gráfica ---
            with st.container(border=True):
                st.markdown("<h3>Serie de nivel</h3>", unsafe_allow_html=True)
                st.plotly_chart(grafico_nivel(df, mascara_outliers), use_container_width=True, config={"displayModeBar": False})

            # --- Eventos de crecida (función nueva) ---
            with st.container(border=True):
                st.markdown("<h3>Eventos de crecida detectados</h3>", unsafe_allow_html=True)
                st.markdown(
                    '<div class="panel-note">Agrupa los outliers consecutivos de la gráfica en episodios de crecida, '
                    'con su fecha de inicio, fin, pico y duración.</div>',
                    unsafe_allow_html=True,
                )
                if eventos.empty:
                    st.markdown('<div class="panel-note">No se detectaron eventos de crecida en este rango de fechas.</div>', unsafe_allow_html=True)
                else:
                    eventos_mostrar = eventos.head(MAX_EVENTOS_MOSTRADOS)
                    filas_html = ""
                    for _, ev in eventos_mostrar.iterrows():
                        filas_html += (
                            f'<div class="evento-fila">'
                            f'<span class="evento-fecha">{ev["inicio"].strftime("%d %b, %H:%M")} → {ev["fin"].strftime("%d %b, %H:%M")} '
                            f'({ev["duracion_h"]:.1f} h)</span>'
                            f'<span class="evento-pico">pico {ev["pico"]:.2f}</span>'
                            f'</div>'
                        )
                    st.markdown(filas_html, unsafe_allow_html=True)
                    if len(eventos) > MAX_EVENTOS_MOSTRADOS:
                        st.markdown(
                            f'<div class="panel-note" style="margin-top:10px;">'
                            f'Mostrando los {MAX_EVENTOS_MOSTRADOS} eventos más recientes de {len(eventos)} detectados en total.</div>',
                            unsafe_allow_html=True,
                        )

            # --- Mapa (sin cambios de estilo respecto a la versión anterior) ---
            with st.container(border=True):
                st.markdown("<h3>Ubicación</h3>", unsafe_allow_html=True)
                if not coords_reales:
                    st.markdown(
                        '<div class="panel-note">No se encontraron coordenadas reales de la estación en la API — '
                        'se muestra el punto de partida (Pascual Bravo) como referencia. Revisa "Datos crudos de la estación" más abajo.</div>',
                        unsafe_allow_html=True,
                    )
                st.pydeck_chart(mapa_estacion(lat, lon, nombre_estacion_api), use_container_width=True)
                st.markdown(
                    f'<div class="coord-readout">lat <span>{lat:.5f}</span> · lon <span>{lon:.5f}</span></div>',
                    unsafe_allow_html=True,
                )

            # --- Fotos ---
            with st.container(border=True):
                st.markdown("<h3>Registro fotográfico</h3>", unsafe_allow_html=True)
                if fotos:
                    imgs_html = "".join(f'<img src="{url}">' for url in fotos)
                    st.markdown(f'<div class="filmstrip">{imgs_html}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<div class="panel-note">No se encontraron fotos de la estación en la respuesta de la API. '
                        'Si sabes que existen, revisa "Datos crudos de la estación" para ubicar el nombre real del campo '
                        'y agrégalo a <code>CANDIDATOS_FOTOS</code>.</div>',
                        unsafe_allow_html=True,
                    )

            # --- Detalle / depuración ---
            with st.expander("Datos crudos de la estación (para depurar)"):
                if info_estacion:
                    st.caption(f"Encontrados en: `{endpoint_usado}`")
                    st.json(info_estacion)
                else:
                    st.write("No se pudo obtener el registro de metadatos de la estación en ninguno de los endpoints probados.")

            with st.expander("Detalle del índice de calidad"):
                st.write(f"- Huecos de reporte detectados: **{huecos}**")
                st.write(f"- Outliers (IQR + nivel negativo): **{n_outliers}** de {len(df)} lecturas")
                st.write("El índice combina completitud de la serie (70%) y proporción de datos sin outliers (30%).")

            with st.expander("Ver datos crudos de la serie"):
                st.dataframe(df, use_container_width=True)

            # --- Descargas (CSV + Excel) ---
            col_csv, col_xlsx = st.columns(2)
            with col_csv:
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar CSV", csv, file_name=f"nivel_estacion_{CODIGO_ESTACION}.csv", mime="text/csv", use_container_width=True)
            with col_xlsx:
                xlsx = exportar_excel(df)
                st.download_button(
                    "Descargar Excel", xlsx, file_name=f"nivel_estacion_{CODIGO_ESTACION}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True,
                )
else:
    st.info("Elige el rango de fechas arriba y presiona **Consultar**.")
