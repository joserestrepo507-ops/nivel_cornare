"""
App básica de Streamlit — Nivel de ríos/quebradas (CORNARE / MARCO)
--------------------------------------------------------------------
Fijada a la estación 23 (José Daniel Restrepo Ramírez). Esta app ya no
permite cambiar de estación: el código queda fijo en CODIGO_ESTACION.

Para correrla:
    streamlit run app_nivel_cornare.py

Nota sobre ubicación y fotos:
El endpoint de "nivel" solo trae fecha/valor, no metadatos de la estación.
Por eso esta app también consulta el LISTADO de estaciones (que sí trae
nombre, coordenadas y -si existen- fotos) y busca ahí la estación 23.
No conozco de antemano los nombres exactos de esas llaves en la API real,
así que se prueban varios nombres comunes (ver CANDIDATOS_* más abajo).
Si al correrla no aparece el título, el mapa o las fotos correctas, abre
el expander "Datos crudos de la estación" para ver las llaves reales y
ajústalas en esas listas.
"""

import requests
import pandas as pd
import numpy as np
import streamlit as st
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ------------------------------------------------------------------
# Estación fija de esta app
# ------------------------------------------------------------------
CODIGO_ESTACION = "23"

# ------------------------------------------------------------------
# Coordenadas por defecto (Institución Universitaria Pascual Bravo)
# Se usan solo si no logramos encontrar la latitud/longitud real.
# ------------------------------------------------------------------
LAT_DEFECTO = 6.2766
LON_DEFECTO = -75.5901

API_BASE_URL = "https://marco.cornare.gov.co/api/v1/estaciones"

LLAVE_FECHA = "level_date"
LLAVE_VALOR = "level"

# Posibles endpoints donde puede vivir el listado/detalle de estaciones
# (se prueban en orden hasta que uno responda 200).
ENDPOINTS_INFO_ESTACION = [
    "{base}/{codigo}/",
    "{base}/{codigo}",
    "{base}/",
]

# Nombres de llave candidatos para cada dato que buscamos.
CANDIDATOS_ID = ["id", "codigo", "code", "station_id", "id_estacion"]
CANDIDATOS_LAT = ["lat", "latitude", "latitud"]
CANDIDATOS_LON = ["lng", "lon", "long", "longitude", "longitud"]
CANDIDATOS_NOMBRE = ["nombre", "name", "station_name", "nombre_estacion"]
CANDIDATOS_FOTOS = [
    "foto", "fotos", "imagen", "imagenes", "photo", "photos",
    "image", "images", "picture", "pictures", "url_foto", "foto_url",
    "imagen_url", "photo_url",
]

st.set_page_config(page_title="Nivel de estación — CORNARE", page_icon="🌊", layout="wide")


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
# Funciones de consulta — metadatos de la estación (nombre, ubicación, fotos)
# ------------------------------------------------------------------
def _valor_por_candidatos(d, candidatos):
    """Devuelve el primer valor encontrado en el dict `d` para cualquiera de las llaves candidatas."""
    if not isinstance(d, dict):
        return None
    for k in candidatos:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _buscar_estacion_en_lista(lista, codigo_estacion):
    """Recorre una lista de estaciones y devuelve la que coincide con el código buscado."""
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
    """
    Intenta obtener el registro de metadatos de la estación (nombre, coordenadas,
    fotos) probando varios endpoints plausibles. Devuelve (dict_o_None, endpoint_usado_o_None).
    """
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

        # Caso 1: el endpoint ya devuelve el detalle de UNA sola estación
        if isinstance(data, dict) and _valor_por_candidatos(data, CANDIDATOS_LAT) is not None:
            return data, url

        # Caso 2: el endpoint devuelve una lista (posiblemente paginada tipo DRF)
        lista = data.get("values") if isinstance(data, dict) else data
        if isinstance(data, dict) and lista is None:
            # a veces el listado viene bajo otra llave, ej. "results" o "estaciones"
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
    """Extrae lat/lon del registro de metadatos. Si no hay, usa el valor por defecto."""
    lat = _valor_por_candidatos(info_estacion, CANDIDATOS_LAT)
    lon = _valor_por_candidatos(info_estacion, CANDIDATOS_LON)
    if lat is not None and lon is not None:
        try:
            return float(lat), float(lon), True
        except (TypeError, ValueError):
            pass
    return LAT_DEFECTO, LON_DEFECTO, False


def detectar_fotos(info_estacion):
    """
    Extrae URLs de fotos del registro de metadatos, aceptando varias formas:
    string único, lista de strings, o lista de dicts con una llave tipo url/foto.
    """
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
                sub_url = _valor_por_candidatos(
                    elem, ["url", "foto", "imagen", "image", "photo", "src", "link"]
                )
                if sub_url:
                    urls.append(sub_url)

    # Filtra vacíos y duplicados conservando el orden
    vistos = set()
    urls_limpias = []
    for u in urls:
        if u and u not in vistos:
            vistos.add(u)
            urls_limpias.append(u)
    return urls_limpias


def calcular_indice_calidad(df):
    """Índice simple (0-100) combinando completitud de la serie y proporción de outliers."""
    if df.empty or len(df) < 2:
        return 0.0, 0, 0

    df_idx = df.set_index("fecha")
    frecuencia_tipica = df["fecha"].diff().dropna().mode()
    if len(frecuencia_tipica) == 0:
        return 0.0, 0, 0
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
    return round(indice, 1), int(huecos), int(es_outlier.sum())


# ------------------------------------------------------------------
# Info de la estación (se obtiene siempre, para poder mostrar el
# nombre real como título aunque el usuario no haya presionado "Consultar")
# ------------------------------------------------------------------
info_estacion, endpoint_usado = obtener_info_estacion(CODIGO_ESTACION)
nombre_estacion_api = _valor_por_candidatos(info_estacion, CANDIDATOS_NOMBRE)
titulo_app = nombre_estacion_api if nombre_estacion_api else f"Estación {CODIGO_ESTACION} — CORNARE"

# ------------------------------------------------------------------
# Sidebar — parámetros de la consulta (editables)
# ------------------------------------------------------------------
st.sidebar.header("Parámetros de tu consulta")
fecha_desde = st.sidebar.date_input("Desde", pd.to_datetime("2026-08-23")).strftime("%Y-%m-%d")
fecha_hasta = st.sidebar.date_input("Hasta", pd.to_datetime("2026-08-30")).strftime("%Y-%m-%d")
calidad = st.sidebar.selectbox("Calidad", [1, 0], index=0, help="1 = solo datos validados")
consultar = st.sidebar.button("🔍 Consultar", type="primary")

st.title(f"🌊 {titulo_app}")
st.caption(f"Estación: **{CODIGO_ESTACION}**")

# ------------------------------------------------------------------
# Consulta y procesamiento
# ------------------------------------------------------------------
if consultar:
    with st.spinner("Consultando la API..."):
        datos_crudos, error = obtener_serie_nivel(CODIGO_ESTACION, fecha_desde, fecha_hasta, calidad)

    if error:
        st.error(f"❌ {error}")
    else:
        registros = obtener_todas_las_paginas(datos_crudos)

        if not registros:
            st.warning("No hay registros para esta estación y rango de fechas. Prueba otro rango de fechas.")
        else:
            df = pd.DataFrame(registros)
            df = df.rename(columns={LLAVE_FECHA: "fecha", LLAVE_VALOR: "nivel"})
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            df["nivel"] = pd.to_numeric(df["nivel"], errors="coerce")
            df = df.dropna(subset=["fecha", "nivel"]).sort_values("fecha").reset_index(drop=True)

            lat, lon, coords_reales = detectar_coordenadas(info_estacion)
            fotos = detectar_fotos(info_estacion)
            indice_calidad, huecos, n_outliers = calcular_indice_calidad(df)

            # --- Métricas principales ---
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Lecturas", len(df))
            col2.metric("Nivel promedio", f"{df['nivel'].mean():.2f}")
            col3.metric("Índice de calidad", f"{indice_calidad} / 100")
            col4.metric("Outliers detectados", n_outliers)

            # --- Gráfico de la serie ---
            st.subheader("Serie de nivel")
            st.line_chart(df.set_index("fecha")["nivel"])

            # --- Mapa de la estación ---
            st.subheader("Ubicación de la estación")
            if not coords_reales:
                st.caption(
                    "No se encontraron coordenadas reales de la estación en la API "
                    "(revisa el expander de datos crudos más abajo para ver las llaves disponibles) "
                    "— se muestra el punto de partida (Pascual Bravo) como referencia."
                )
            st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=12)

            # --- Fotos de la estación ---
            st.subheader("Fotos de la estación")
            if fotos:
                cols_fotos = st.columns(min(len(fotos), 3))
                for i, url_foto in enumerate(fotos):
                    with cols_fotos[i % len(cols_fotos)]:
                        st.image(url_foto, use_container_width=True)
            else:
                st.caption(
                    "No se encontraron fotos de la estación en la respuesta de la API. "
                    "Si sabes que sí existen, revisa el expander de datos crudos para "
                    "identificar el nombre real del campo y agrégalo a `CANDIDATOS_FOTOS`."
                )

            # --- Datos crudos de la estación (para depurar nombres de campos) ---
            with st.expander("🔍 Datos crudos de la estación (para depurar)"):
                if info_estacion:
                    st.caption(f"Encontrados en: `{endpoint_usado}`")
                    st.json(info_estacion)
                else:
                    st.write("No se pudo obtener el registro de metadatos de la estación en ninguno de los endpoints probados.")

            # --- Detalle de calidad ---
            with st.expander("Detalle del índice de calidad"):
                st.write(f"- Huecos de reporte detectados: **{huecos}**")
                st.write(f"- Outliers (IQR + nivel negativo): **{n_outliers}** de {len(df)} lecturas")
                st.write("El índice combina completitud de la serie (70%) y proporción de datos sin outliers (30%).")

            # --- Tabla y descarga ---
            with st.expander("Ver datos crudos de la serie"):
                st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Descargar CSV", csv, file_name=f"nivel_estacion_{CODIGO_ESTACION}.csv", mime="text/csv")
else:
    st.info("Ajusta el rango de fechas en el sidebar y presiona **Consultar**.")
