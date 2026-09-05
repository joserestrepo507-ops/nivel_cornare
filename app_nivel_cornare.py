"""
Panel de estación — Nivel de ríos/quebradas (CORNARE / MARCO)
--------------------------------------------------------------------
Fijada a la estación 23 (José Daniel Restrepo Ramírez). El código de
estación no es editable: vive en CODIGO_ESTACION.

Para correrla (recuerda mantener la carpeta .streamlit/ junto a este
archivo para que cargue el tema oscuro):
    streamlit run app_nivel_cornare.py

Requiere: streamlit>=1.25 (para mapas pydeck con estilo oscuro sin
token de Mapbox), pandas, numpy, requests, plotly, pydeck.

Nota sobre ubicación y fotos:
El endpoint de "nivel" solo trae fecha/valor, no metadatos de la
estación. Por eso esta app también consulta el LISTADO de estaciones
(que sí trae nombre, coordenadas y -si existen- fotos) y busca ahí la
estación 23. No conozco de antemano los nombres exactos de esas llaves
en la API real, así que se prueban varios nombres comunes (ver
CANDIDATOS_* más abajo). Si el mapa, el título o las fotos no salen
bien, abre "Datos crudos de la estación" para ver las llaves reales
y ajústalas ahí.
"""

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
CANDIDATOS_FOTOS = [
    "foto", "fotos", "imagen", "imagenes", "photo", "photos",
    "image", "images", "picture", "pictures", "url_foto", "foto_url",
    "imagen_url", "photo_url",
]

# ------------------------------------------------------------------
# Paleta y tipografía — panel de instrumento hidrométrico
# ------------------------------------------------------------------
BG = "#101B1A"
PANEL = "#16211F"
LINE = "#283B39"
TEXT = "#EAF3F1"
MUTED = "#86A19E"
ACCENT = "#57C3D3"
ACCENT_WARM = "#D98B4A"

st.set_page_config(page_title="Estación 23", page_icon="🌊", layout="wide")

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}

    .stApp {{
        background: {BG};
    }}

    /* ---------- encabezado ---------- */
    .panel-hero {{
        padding: 6px 0 26px 0;
        border-bottom: 1px solid {LINE};
        margin-bottom: 28px;
    }}
    .panel-hero h1 {{
        font-family: 'Fraunces', serif;
        font-weight: 500;
        font-size: 2.6rem;
        line-height: 1.15;
        color: {TEXT};
        margin: 0 0 8px 0;
    }}
    .panel-hero p {{
        color: {MUTED};
        font-size: 0.98rem;
        margin: 0;
        max-width: 60ch;
    }}

    /* ---------- franja de lecturas tipo instrumento ---------- */
    .readout-strip {{
        display: flex;
        flex-wrap: wrap;
        border-top: 1px solid {LINE};
        border-bottom: 1px solid {LINE};
        margin: 26px 0 34px 0;
    }}
    .readout {{
        flex: 1 1 160px;
        padding: 16px 22px;
        border-right: 1px solid {LINE};
    }}
    .readout:last-child {{ border-right: none; }}
    .readout-label {{
        color: {MUTED};
        font-size: 0.8rem;
        margin-bottom: 6px;
    }}
    .readout-value {{
        color: {TEXT};
        font-size: 1.9rem;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.01em;
    }}
    .readout-value.warm {{ color: {ACCENT_WARM}; }}

    /* ---------- paneles de contenido ---------- */
    .panel-block {{
        border: 1px solid {LINE};
        background: {PANEL};
        padding: 22px 24px 8px 24px;
        margin-bottom: 26px;
    }}
    .panel-block h3 {{
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 1.02rem;
        color: {TEXT};
        margin: 0 0 4px 0;
    }}
    .panel-block .panel-note {{
        color: {MUTED};
        font-size: 0.88rem;
        margin-bottom: 14px;
    }}
    .coord-readout {{
        font-variant-numeric: tabular-nums;
        color: {MUTED};
        font-size: 0.85rem;
        padding: 10px 0 18px 0;
    }}
    .coord-readout span {{ color: {ACCENT}; }}

    /* ---------- tira de fotos ---------- */
    .filmstrip {{
        display: flex;
        gap: 12px;
        overflow-x: auto;
        padding-bottom: 12px;
    }}
    .filmstrip img {{
        height: 210px;
        width: auto;
        object-fit: cover;
        border: 1px solid {LINE};
        flex-shrink: 0;
    }}

    /* ---------- barra de control ---------- */
    .control-label {{
        color: {MUTED};
        font-size: 0.8rem;
        margin-bottom: 10px;
    }}

    /* ---------- widgets nativos ---------- */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: {PANEL};
        border-color: {LINE} !important;
    }}
    [data-testid="stButton"] button, [data-testid="stDownloadButton"] button {{
        background: {ACCENT};
        color: {BG};
        border: none;
        border-radius: 2px;
        font-weight: 600;
    }}
    [data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover {{
        background: {TEXT};
        color: {BG};
    }}
    [data-testid="stExpander"] {{
        border: 1px solid {LINE};
        background: {PANEL};
    }}
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


def grafico_nivel(df, es_outlier):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["fecha"], y=df["nivel"],
        mode="lines", name="Nivel",
        line=dict(color=ACCENT, width=1.6),
        fill="tozeroy", fillcolor="rgba(87, 195, 211, 0.12)",
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


# ------------------------------------------------------------------
# Info de la estación — se obtiene siempre, así el título ya sale
# con el nombre real aunque el usuario no haya presionado "Consultar"
# ------------------------------------------------------------------
info_estacion, endpoint_usado = obtener_info_estacion(CODIGO_ESTACION)
nombre_estacion_api = _valor_por_candidatos(info_estacion, CANDIDATOS_NOMBRE)
titulo_app = nombre_estacion_api if nombre_estacion_api else f"Estación {CODIGO_ESTACION}"

# ------------------------------------------------------------------
# Encabezado
# ------------------------------------------------------------------
st.markdown(
    f"""
    <div class="panel-hero">
        <h1>{titulo_app}</h1>
        <p>Estación limnimétrica del sistema MARCO, operado por Cornare, en la cuenca de los ríos Negro y Nare.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# Barra de control — en el panel principal, sin fechas predeterminadas
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
            df["nivel"] = pd.to_numeric(df["nivel"], errors="coerce")
            df = df.dropna(subset=["fecha", "nivel"]).sort_values("fecha").reset_index(drop=True)

            lat, lon, coords_reales = detectar_coordenadas(info_estacion)
            fotos = detectar_fotos(info_estacion)
            indice_calidad, huecos, n_outliers, mascara_outliers = calcular_calidad(df)

            # --- Franja de lecturas ---
            st.markdown(
                f"""
                <div class="readout-strip">
                    <div class="readout">
                        <div class="readout-label">Lecturas</div>
                        <div class="readout-value">{len(df):,}</div>
                    </div>
                    <div class="readout">
                        <div class="readout-label">Nivel promedio</div>
                        <div class="readout-value">{df['nivel'].mean():.2f}</div>
                    </div>
                    <div class="readout">
                        <div class="readout-label">Índice de calidad</div>
                        <div class="readout-value">{indice_calidad}<span style="font-size:1.1rem;color:{MUTED};"> /100</span></div>
                    </div>
                    <div class="readout">
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

            # --- Mapa ---
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

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Descargar CSV", csv, file_name=f"nivel_estacion_{CODIGO_ESTACION}.csv", mime="text/csv")
else:
    st.info("Elige el rango de fechas arriba y presiona **Consultar**.")
