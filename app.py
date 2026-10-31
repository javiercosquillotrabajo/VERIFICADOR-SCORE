import streamlit as st
import pdfplumber
import re
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

st.set_page_config(
    page_title="Verificación de Score",
    page_icon="💳",
    layout="wide"
)

css = (
    "<style>"
    ".stApp { background-color: #0b111e; color: #ffffff; }"
    ".tier-card { padding: 14px 18px; border-radius: 10px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; font-family: sans-serif; font-weight: 600; font-size: 15px; opacity: 0.35; transition: all 0.3s ease; }"
    ".tier-active { opacity: 1 !important; transform: scale(1.03); box-shadow: 0px 0px 20px rgba(255, 255, 255, 0.25); }"
    ".circle-container { width: 240px; height: 240px; border-radius: 50%; margin: 20px auto; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #131c2e; }"
    ".circle-score { font-size: 60px; font-weight: 800; line-height: 1; margin: 5px 0; }"
    ".fintech-card { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 25px; max-width: 650px; margin: 0 auto 25px auto; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }"
    ".diag-box { background: #1e293b; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid rgba(255,255,255,0.08); }"
    ".cert-container { background: #ffffff; color: #1e3a8a; padding: 35px; border-radius: 12px; border-top: 8px solid #1e3a8a; max-width: 750px; margin: 0 auto; box-shadow: 0 8px 30px rgba(0,0,0,0.3); font-family: sans-serif; }"
    ".cert-score-box { background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0; }"
    ".progress-bar-container { display: flex; height: 14px; border-radius: 7px; overflow: hidden; margin: 15px 0 5px 0; }"
    ".timeline-card { background: #131c2e; border: 1.5px solid #1e293b; border-radius: 14px; padding: 14px 6px; text-align: center; margin: 3px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }"
    ".timeline-dot { width: 26px; height: 26px; border-radius: 50%; margin: 10px auto; box-shadow: 0 0 12px rgba(255,255,255,0.25); }"
    "</style>"
)
st.markdown(css, unsafe_allow_html=True)

RANGOS = [
    {"label": "Excelente Puntaje", "min": 877, "max": 999, "color": "#00c875", "rango_texto": "877 - 999", "prob_prestamo": "Alta (Preferencial)", "tarjetas": "Líneas altas", "riesgo": "Mínimo"},
    {"label": "Buen Puntaje",      "min": 722, "max": 876, "color": "#1db954", "rango_texto": "722 - 876", "prob_prestamo": "Alta", "tarjetas": "Aprobación Rápida", "riesgo": "Bajo"},
    {"label": "Puntaje Medio",     "min": 598, "max": 721, "color": "#f59e0b", "rango_texto": "598 - 721", "prob_prestamo": "Media (Sujeto a eval.)", "tarjetas": "Límites moderados", "riesgo": "Moderado"},
    {"label": "Puntaje Bajo",      "min": 477, "max": 597, "color": "#e67e22", "rango_texto": "477 - 597", "prob_prestamo": "Baja", "tarjetas": "Con garantía / fianza", "riesgo": "Alto"},
    {"label": "Puntaje Muy Bajo",  "min": 0,   "max": 476, "color": "#e74c3c", "rango_texto": "0 - 476",   "prob_prestamo": "No Apto", "tarjetas": "Restringidas", "riesgo": "Crítico"},
]

COLORES_SEMAFORO = {
    "Verde": {"hex": "#10b981", "desc": "VERDE"},
    "Gris": {"hex": "#94a3b8", "desc": "GRIS"},
    "Amarillo": {"hex": "#f59e0b", "desc": "AMARILLO"},
    "Rojo": {"hex": "#ef4444", "desc": "ROJO"}
}

MESES_NOMBRES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
MESES_MAP = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

def clasificar_score(score):
    for r in RANGOS:
        if r["min"] <= score <= r["max"]:
            return r
    return RANGOS[-1]

def extraer_score_experian(pagina):
    texto_p1 = pagina.extract_text() or ""
    if re.search(r"excluid[oa]|exclusi[oó]n", texto_p1, re.IGNORECASE):
        return 0

    m = re.search(r"(?:score\s+experian|puntaje)[^\d]{0,40}?(\b[1-9]\d{2}\b)", texto_p1, re.IGNORECASE)
    if m:
        valor = int(m.group(1))
        return 0 if valor == 92 else valor

    m2 = re.search(r"(\b[1-9]\d{2}\b)[\s\n]*puntaje", texto_p1, re.IGNORECASE)
    if m2:
        valor = int(m2.group(1))
        return 0 if valor == 92 else valor

    ancho = pagina.width
    palabras = pagina.extract_words()
    candidatos = []
    for w in palabras:
        t = w["text"].strip()
        if t.isdigit() and len(t) == 3 and w["x0"] > (ancho * 0.5):
            candidatos.append((w["top"], int(t)))

    if candidatos:
        candidatos.sort(key=lambda x: x[0])
        valor = candidatos[0][1]
        return 0 if valor == 92 else valor

    return 0

def extraer_nombre(pdf):
    texto = ""
    for pag in pdf.pages[:2]:
        t = pag.extract_text()
        if t:
            texto += t + "\n"

    match_cab = re.search(r"DNI\s+\d{8}\s*-\s*([A-ZÁÉÍÓÚÑ\s]+)", texto)
    if match_cab:
        palabras = [p for p in match_cab.group(1).split() if len(p) > 2]
        if len(palabras) >= 3:
            return palabras[2].upper()
        elif palabras:
            return palabras[-1].upper()

    lineas = texto.splitlines()
    palabras_a_ignorar = {"NOMBRES", "NOMBRE", "DATOS", "PERSONALES", "APELLIDOS", "APELLIDO", "DNI"}
    for i, linea in enumerate(lineas):
        if re.search(r"\bNOMBRES?\b", linea, re.IGNORECASE):
            texto_fila = linea + (" " + lineas[i+1] if i+1 < len(lineas) else "")
            palabras = [p for p in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", texto_fila) if p.upper() not in palabras_a_ignorar and len(p) > 1]
            if palabras:
                return palabras[-1].upper()

    return "CLIENTE"

def extraer_semaforo_12m(pdf):
    texto_total = ""
    pag_semaforo = None
    for idx_p, pag in enumerate(pdf.pages):
        t = pag.extract_text() or ""
        texto_total += t + "\n"
        if re.search(r"sem[aá]foros?\s+de\s+los", t, re.IGNORECASE) or ("semáforo" in t.lower() and "24" in t.lower()):
            pag_semaforo = pag
            break

    if pag_semaforo is None:
        pag_semaforo = pdf.pages[1] if len(pdf.pages) > 1 else pdf.pages[0]

    # Calcular los últimos 12 meses exactos a partir de la fecha del reporte
    m_fecha = re.search(r"actualizada\s+al[:\s]+(?:\d{1,2}\s+de\s+)?([a-záéíóú]+)\s+del?\s+(\d{4})", texto_total, re.IGNORECASE)
    mes_fin = 10
    anio_fin = 2026
    if m_fecha:
        mes_str = m_fecha.group(1).lower().strip()
        anio_fin = int(m_fecha.group(2))
        mes_fin = MESES_MAP.get(mes_str, 10)

    ultimos_12_meses = []
    for k in range(11, -1, -1):
        total_m = (anio_fin * 12 + (mes_fin - 1)) - k
        a = total_m // 12
        m_idx = total_m % 12
        ultimos_12_meses.append(f"{MESES_NOMBRES[m_idx]}-{a}")

    # Método 1: Búsqueda de tabla SBS textual
    colores_tabla = []
    lineas = texto_total.splitlines()
    for linea in lineas:
        if re.search(r"\b(?:NOR|CPP|DEF|DUD|PER|S/INF)\b", linea, re.IGNORECASE):
            codigos = re.findall(r"\b(NOR|CPP|DEF|DUD|PER|S/INF)\b", linea, re.IGNORECASE)
            if len(codigos) >= 12:
                for c in codigos[-12:]:
                    c_up = c.upper()
                    if c_up == "NOR":
                        colores_tabla.append("Verde")
                    elif c_up == "CPP":
                        colores_tabla.append("Amarillo")
                    elif c_up in ["DEF", "DUD", "PER"]:
                        colores_tabla.append("Rojo")
                    else:
                        colores_tabla.append("Gris")
                break

    if len(colores_tabla) == 12:
        return [{"mes": m, "color": c} for m, c in zip(ultimos_12_meses, colores_tabla)]

    # Método 2: Extracción de puntos gráficos
    candidatos = []
    ancho = pag_semaforo.width
    for obj in (pag_semaforo.curves + pag_semaforo.rects):
        w = obj.get("width", 0)
        h = obj.get("height", 0)
        top = obj.get("top", 0)
        x0 = obj.get("x0", 0)

        if 1 <= w <= 65 and 1 <= h <= 65:
            raw_c = obj.get("non_stroking_color") or obj.get("stroking_color")
            candidatos.append({
                "x": x0 + w / 2,
                "y": top + h / 2,
                "color_raw": raw_c
            })

    # Separar puntos del eje vs puntos de la serie mensual
    ref_eje = [c for c in candidatos if c["x"] < ancho * 0.18]
    puntos_grafico = [c for c in candidatos if c["x"] >= ancho * 0.18]
    puntos_grafico.sort(key=lambda p: p["x"])

    # Agrupar columnas por mes
    columnas_mes = []
    for p in puntos_grafico:
        if not columnas_mes or abs(p["x"] - columnas_mes[-1]["x"]) > 6:
            columnas_mes.append(p)
        else:
            if p["color_raw"] and not columnas_mes[-1]["color_raw"]:
                columnas_mes[-1] = p

    ref_eje.sort(key=lambda p: p["y"])
    if len(ref_eje) >= 4:
        y_verde = ref_eje[0]["y"]
        y_gris = ref_eje[1]["y"]
        y_amarillo = ref_eje[2]["y"]
        y_rojo = ref_eje[3]["y"]
    elif columnas_mes:
        y_vals = [p["y"] for p in columnas_mes]
        min_y, max_y = min(y_vals), max(y_vals)
        paso = (max_y - min_y) / 3 if max_y > min_y else 1
        y_verde = min_y
        y_gris = min_y + paso
        y_amarillo = min_y + paso * 2
        y_rojo = max_y
    else:
        y_verde, y_gris, y_amarillo, y_rojo = 100, 135, 170, 205

    def punto_a_color(p):
        raw = p.get("color_raw")
        if isinstance(raw, (tuple, list)) and len(raw) >= 3:
            r, g, b = raw[:3]
            if r > 0.65 and g < 0.4:
                return "Rojo"
            elif r > 0.65 and g > 0.55:
                return "Amarillo"
            elif g > 0.
