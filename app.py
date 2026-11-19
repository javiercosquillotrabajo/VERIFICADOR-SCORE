import streamlit as st
import pdfplumber
import re
import time
import io
import urllib.parse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas

st.set_page_config(
    page_title="Verificación de Score",
    page_icon="💳",
    layout="wide"
)

css_base = (
    "<style>"
    ".stApp { background-color: #0a0f1d; color: #ffffff; -webkit-font-smoothing: antialiased; }"
    "h1, h2, h3, h4, h5, p, span { font-family: 'Segoe UI', Tahoma, Arial, sans-serif; }"
    "div[data-testid='column']:nth-of-type(1) {"
    "  background: #111a2e;"
    "  border: 3px solid #38bdf8;"
    "  border-radius: 24px;"
    "  padding: 26px 20px;"
    "  box-shadow: 0 15px 45px rgba(0,0,0,0.6);"
    "}"
    "div[data-testid='stTextInput'] label p, div[data-testid='stNumberInput'] label p, div[data-testid='stFileUploader'] label p {"
    "  font-size: 24px !important; font-weight: 900 !important; color: #38bdf8 !important; margin-bottom: 6px !important;"
    "}"
    "div[data-testid='stTextInput'] input, div[data-testid='stNumberInput'] input {"
    "  font-size: 32px !important; font-weight: 900 !important; height: 70px !important; color: #ffffff !important; background-color: #0f172a !important; border: 3px solid #38bdf8 !important; border-radius: 18px !important; padding: 10px 18px !important;"
    "}"
    "div[data-testid='stRadio'] label p, div[data-testid='stRadio'] label span, div[data-testid='stRadio'] label {"
    "  font-size: 22px !important; font-weight: 900 !important; color: #ffffff !important; line-height: 1.4 !important; padding-left: 8px !important;"
    "}"
    "div[data-testid='stRadio'] > div {"
    "  background: #0f172a !important; border: 2.5px solid #38bdf8 !important; border-radius: 20px !important; padding: 16px 18px !important; gap: 14px !important;"
    "}"
    "div[data-testid='stFileUploader'] section div, div[data-testid='stFileUploader'] section span {"
    "  font-size: 18px !important; font-weight: 800 !important; color: #e2e8f0 !important;"
    "}"
    "div[data-testid='stButton'] button, div[data-testid='stButton'] button p {"
    "  font-size: 22px !important; font-weight: 900 !important;"
    "}"
    "div[data-testid='stButton'] button {"
    "  padding: 18px 14px !important; border-radius: 18px !important; margin-top: 8px !important; height: auto !important;"
    "}"
    "div[data-testid='stButton'] button[kind='secondary'] {"
    "  background-color: #1e293b !important; border: 2.5px solid #fbbf24 !important;"
    "}"
    "div[data-testid='stButton'] button[kind='secondary'] p {"
    "  color: #fbbf24 !important;"
    "}"
    ".hero-card { background: #151e32; border: 2.5px solid #334155; border-radius: 26px; padding: 30px 22px; margin: 15px auto; max-width: 650px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); text-align: center; }"
    ".circle-container { width: 240px; height: 240px; border-radius: 50%; margin: 16px auto; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #0f172a; box-shadow: 0 15px 40px rgba(0,0,0,0.4); }"
    ".circle-score { font-size: 86px; font-weight: 900; line-height: 1; margin: 2px 0; }"
    ".brick-container { display: flex; gap: 8px; justify-content: space-between; margin-top: 18px; }"
    ".brick-pill { flex: 1; padding: 14px 4px; border-radius: 14px; text-align: center; opacity: 0.45; transition: all 0.25s ease; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }"
    ".brick-pill-active { opacity: 1 !important; transform: scale(1.12); box-shadow: 0 0 30px currentColor !important; border: 3px solid #ffffff !important; }"
    ".stacked-bar { padding: 16px 22px; border-radius: 16px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; font-weight: 900; font-size: 20px; opacity: 0.45; transition: all 0.2s ease; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }"
    ".stacked-bar-active { opacity: 1 !important; transform: scale(1.04); box-shadow: 0 0 30px currentColor !important; border: 3.5px solid #ffffff !important; }"
    ".bank-card { background: #151e32; border: 2px solid #334155; border-radius: 18px; padding: 18px 22px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 8px 25px rgba(0,0,0,0.3); text-align: left; }"
    ".bank-badge { padding: 10px 18px; border-radius: 22px; font-weight: 900; font-size: 15px; color: #ffffff; text-align: center; }"
    ".total-deuda-banner { background: linear-gradient(135deg, #1e40af, #0f172a); border-radius: 20px; padding: 20px 26px; color: white; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border: 2px solid #38bdf8; }"
    ".total-vencidos-banner { background: linear-gradient(135deg, #b91c1c, #450a0a); border-radius: 20px; padding: 20px 26px; color: white; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border: 2px solid #f87171; }"
    "</style>"
)
st.markdown(css_base, unsafe_allow_html=True)

# ESCALA OFICIAL (Orden estándar de Excelente a Muy Bajo)
RANGOS = [
    {"label": "Excelente Puntaje", "min": 877, "max": 999, "color": "#00e676", "texto_col": "#000000", "rango_texto": "877 - 999", "corto": "Excelente", "orden": 5},
    {"label": "Buen Puntaje",      "min": 722, "max": 876, "color": "#10b981", "texto_col": "#ffffff", "rango_texto": "722 - 876", "corto": "Bueno",     "orden": 4},
    {"label": "Puntaje Medio",     "min": 598, "max": 721, "color": "#fbbf24", "texto_col": "#000000", "rango_texto": "598 - 721", "corto": "Medio",     "orden": 3},
    {"label": "Puntaje Bajo",      "min": 477, "max": 597, "color": "#f97316", "texto_col": "#ffffff", "rango_texto": "477 - 597", "corto": "Bajo",      "orden": 2},
    {"label": "Puntaje Muy Bajo",  "min": 0,   "max": 476, "color": "#ef4444", "texto_col": "#ffffff", "rango_texto": "0 - 476",   "corto": "Muy Bajo",  "orden": 1},
]

# LADRILLOS HORIZONTALES: DE IZQUIERDA (ROJO) A DERECHA (VERDE)
LADRILLOS_ROJO_A_VERDE = [
    {"label": "Puntaje Muy Bajo", "rango": "0 - 476",   "nombre": "MUY BAJO",  "color": "#ef4444", "texto": "#ffffff"},
    {"label": "Puntaje Bajo",     "rango": "477 - 597", "nombre": "BAJO",      "color": "#f97316", "texto": "#ffffff"},
    {"label": "Puntaje Medio",    "rango": "598 - 721", "nombre": "MEDIO",     "color": "#fbbf24", "texto": "#000000"},
    {"label": "Buen Puntaje",     "rango": "722 - 876", "nombre": "BUENO",     "color": "#10b981", "texto": "#ffffff"},
    {"label": "Excelente Puntaje","rango": "877 - 999", "nombre": "EXCELENTE", "color": "#00e676", "texto": "#000000"},
]

COLORES_SBS = {
    "NOR": {"nombre": "NORMAL", "color": "#00e676", "texto": "#000000"},
    "CPP": {"nombre": "CPP", "color": "#fbbf24", "texto": "#000000"},
    "DEF": {"nombre": "DEFICIENTE", "color": "#f97316", "texto": "#ffffff"},
    "DUD": {"nombre": "DUDOSO", "color": "#ef4444", "texto": "#ffffff"},
    "PER": {"nombre": "PÉRDIDA", "color": "#ef4444", "texto": "#ffffff"},
    "SCAL": {"nombre": "SIN CALIF.", "color": "#64748b", "texto": "#ffffff"}
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
        if valor == 92:
            return 0
        return valor

    m2 = re.search(r"(\b[1-9]\d{2}\b)[\s\n]*puntaje", texto_p1, re.IGNORECASE)
    if m2:
        valor = int(m2.group(1))
        if valor == 92:
            return 0
        return valor

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
        if valor == 92:
            return 0
        return valor

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
        if palabras:
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

def extraer_deudas_sbs(pdf):
    deudas = []
    paginas = []
    if len(pdf.pages) >= 3:
        paginas.append(pdf.pages[2])
    for p in pdf.pages:
        if p not in paginas:
            paginas.append(p)

    for pag in paginas:
        palabras = pag.extract_words()
        if not palabras:
            continue

        filas = []
        for w in sorted(palabras, key=lambda x: (x["top"], x["x0"])):
            if not filas or abs(w["top"] - filas[-1][0]["top"]) > 5:
                filas.append([w])
            else:
                filas[-1].append(w)

        lineas_visuales = []
        for f in filas:
            f_ord = sorted(f, key=lambda x: x["x0"])
            txt_fila = " ".join([w["text"] for w in f_ord])
            lineas_visuales.append(txt_fila)

        en_tabla = False
        for l in lineas_visuales:
            l_strip = l.strip()
            if "Detalle de la deuda SBS" in l_strip or "SBS/Microfinanzas" in l_strip:
                en_tabla = True
                continue

            if en_tabla:
                if "TOTAL" in l_strip.upper() or "Detalle de vencidos" in l_strip or "Utilización de Líneas" in l_strip:
                    en_tabla = False
                    break

                m_match = re.search(r"\b(NOR|CPP|DEF|DUD|PER|SCAL)\b\s+([\d,]+\.\d{2})(?:\s+(\d{1,4}))?", l_strip)
                if m_match:
                    calif = m_match.group(1).upper()
                    monto = m_match.group(2)
                    dias = m_match.group(3) if m_match.group(3) else "0"

                    parte_antes = l_strip[:m_match.start()].strip()
                    m_banco = re.search(r"^([A-ZÁÉÍÓÚÑa-záéíóúñ\s\.\/\-\&]+?)(?=\s+[\d,]+\.\d{2}|\s+\d{2}\/\d{2}\/\d{4})", parte_antes)
                    if m_banco:
                        banco_nom = m_banco.group(1).strip()
                    else:
                        palabras_antes = parte_antes.split()
                        banco_nom = " ".join([p for p in palabras_antes if not re.search(r"\d", p)])

                    if banco_nom and "ENTIDAD" not in banco_nom.upper() and "DETALLE" not in banco_nom.upper():
                        deudas.append({
                            "banco": banco_nom,
                            "monto": monto,
                            "calif": calif,
                            "dias": dias
                        })

        if deudas:
            break

    return deudas

def extraer_otras_deudas(pdf):
    vencidos = []
    paginas = []
    if len(pdf.pages) >= 3:
        paginas.append(pdf.pages[2])
    for p in pdf.pages:
        if p not in paginas:
            paginas.append(p)

    for pag in paginas:
        palabras = pag.extract_words()
        if not palabras:
            continue

        filas = []
        for w in sorted(palabras, key=lambda x: (x["top"], x["x0"])):
            if not filas or abs(w["top"] - filas[-1][0]["top"]) > 5:
                filas.append([w])
            else:
                filas[-1].append(w)

        lineas_visuales = []
        for f in filas:
            f_ord = sorted(f, key=lambda x: x["x0"])
            txt_fila = " ".join([w["text"] for w in f_ord])
            lineas_visuales.append(txt_fila)

        en_vencidos = False
        for l in lineas_visuales:
            l_strip = l.strip()
            if "Detalle de vencidos" in l_strip or "Documentos impagos" in l_strip or "Protestos" in l_strip:
                en_vencidos = True
                continue

            if en_vencidos:
                if "Utilización de Líneas" in l_strip or "Otros documentos" in l_strip or "TOTAL" in l_strip.upper():
                    en_vencidos = False
                    break

                m_monto = re.search(r"([\d,]+\.\d{2})", l_strip)
                if m_monto:
                    monto_val = m_monto.group(1)
                    pos_monto = m_monto.start()
                    parte_izq = l_strip[:pos_monto].strip()
                    resto_der = l_strip[m_monto.end():].strip()
                    m_dias = re.search(r"\b(\d{1,4})\b", resto_der)
                    dias_val = m_dias.group(1) if m_dias else "30+"
                    acreedor_nom = re.sub(r"^\d+\s+", "", parte_izq).strip()
                    acreedor_nom = re.sub(r"^(#Doc|Fuente|Acreedor|Monto|Dias)\s*", "", acreedor_nom, flags=re.IGNORECASE).strip()

                    if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", acreedor_nom):
                        continue
                    try:
                        val_num = float(monto_val.replace(",", ""))
                        if val_num <= 0.0:
                            continue
                    except:
                        pass

                    if acreedor_nom and len(acreedor_nom) > 2:
                        vencidos.append({
                            "acreedor": acreedor_nom,
                            "monto": monto_val,
                            "dias": dias_val
                        })

        if vencidos:
            break

    return vencidos

# Inicialización de estados
if "live_nombre" not in st.session_state:
    st.session_state["live_nombre"] = "CLIENTE"
if "live_score" not in st.session_state:
    st.session_state["live_score"] = 650
if "live_deudas" not in st.session_state:
    st.session_state["live_deudas"] = []
if "live_vencidos" not in st.session_state:
    st.session_state["live_vencidos"] = []
if "estilo_seleccionado" not in st.session_state:
    st.session_state["estilo_seleccionado"] = "1. Ladrillos Horizontales"

col_panel, col_display = st.columns([1.1, 2.3], gap="large")

# =========================================================================
# 🎛️ LADO IZQUIERDO: PANEL DE CONTROL EN LETRAS GIGANTES Y MÁXIMA NITIDEZ
# =========================================================================
with col_panel:
    st.markdown("<h1 style='margin:0 0 2px 0; color:#38bdf8; font-size:32px; font-weight:900;'>🎛️ PANEL PRIVADO</h1>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:16px; color:#94a3b8; font-weight:bold; margin-bottom:14px;'>Consola de control (fuera de cámara).</p>", unsafe_allow_html=True)

    uploaded_file = st.file_uploader("📂 Adjuntar reporte PDF", type=["pdf"])

    detected_nombre = st.session_state["live_nombre"]
    detected_score = st.session_state["live_score"]
    detected_deudas = st.session_state["live_deudas"]
    detected_vencidos = st.session_state["live_vencidos"]

    if uploaded_file:
        with pdfplumber.open(uploaded_file) as pdf:
            s = extraer_score_experian(pdf.pages[0])
            n = extraer_nombre(pdf)
            d_sbs = extraer_deudas_sbs(pdf)
            d_venc = extraer_otras_deudas(pdf)
            if s is not None:
                detected_score = s
            if n:
                detected_nombre = n
            detected_deudas = d_sbs if d_sbs else []
            detected_vencidos = d_venc if d_venc else []

    st.write("")
    nombre_ctrl = st.text_input("Nombre del Cliente:", value=detected_nombre)
    st.write("")
    score_ctrl = st.number_input("Score / Puntaje:", min_value=0, max_value=999, value=detected_score)
    score_final_ctrl = 0 if score_ctrl == 92 else score_ctrl

    st.write("")
    st.markdown("<p style='font-size:24px; font-weight:900; color:#38bdf8; margin: 12px 0 8px 0;'>📺 Vista para la transmisión:</p>", unsafe_allow_html=True)

    opciones_vistas = ["1. Ladrillos Horizontales", "2. Niveles Verticales", "3. Deudas Bancarias", "4. Otras Deudas"]
    idx_def = opciones_vistas.index(st.session_state["estilo_seleccionado"]) if st.session_state["estilo_seleccionado"] in opciones_vistas else 0

    estilo_sel = st.radio(
        "Seleccionar vista:",
        opciones_vistas,
        index=idx_def,
        label_visibility="collapsed"
    )
    st.session_state["estilo_seleccionado"] = estilo_sel

    st.markdown("<div style='margin-top:18px;'></div>", unsafe_allow_html=True)
    if st.button("🚀 TRANSMITIR EN VIVO", use_container_width=True, type="primary"):
        st.session_state["live_nombre"] = nombre_ctrl
        st.session_state["live_score"] = score_final_ctrl
        st.session_state["live_deudas"] = detected_deudas
        st.session_state["live_vencidos"] = detected_vencidos
        st.rerun()

    st.markdown("<hr style='border-color:#334155; margin:22px 0;'>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:#0f172a; border:2.5px solid #334155; border-radius:18px; padding:16px 18px; margin-bottom:12px;'>"
        f"<div style='font-size:18px; font-weight:900; color:#00e676; margin-bottom:4px;'>🏦 DEUDAS SBS:</div>"
        f"<div style='font-size:26px; font-weight:900; color:#ffffff;'>{len(detected_deudas)} detectadas</div>"
        f"</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<div style='background:#0f172a; border:2.5px solid #334155; border-radius:18px; padding:16px 18px;'>"
        f"<div style='font-size:18px; font-weight:900; color:#f87171; margin-bottom:4px;'>⚠️ OTRAS DEUDAS:</div>"
        f"<div style='font-size:26px; font-weight:900; color:#ffffff;'>{len(detected_vencidos)} detectadas</div>"
        f"</div>",
        unsafe_allow_html=True
    )

# =========================================================================
# 📺 LADO DERECHO: PANTALLA EN VIVO 100% LIMPIA
# =========================================================================
with col_display:
    nombre_show = st.session_state["live_nombre"]
    score_show = st.session_state["live_score"]
    deudas_show = st.session_state["live_deudas"]
    vencidos_show = st.session_state["live_vencidos"]
    estilo_activo = st.session_state["estilo_seleccionado"]

    cat_show = clasificar_score(score_show)

    # ==================== VISTA 1: LADRILLOS HORIZONTALES (ROJO A VERDE) ====================
    if estilo_activo == "1. Ladrillos Horizontales":
        html_ladrillos = ""
        for b in LADRILLOS_ROJO_A_VERDE:
            es_act = (b["label"] == cat_show["label"])
            clase_b = "brick-pill brick-pill-active" if es_act else "brick-pill"
            html_ladrillos += (
                f'<div class="{clase_b}" style="background-color: {b["color"]}; color: {b["texto"]} !important;">'
                f'<div style="font-size: 15px; font-weight: 900; margin-bottom: 2px;">{b["nombre"]}</div>'
                f'<div style="font-size: 11px; font-weight: 800; opacity: 0.95;">{b["rango"]}</div>'
                f'</div>'
            )

        card_bloques = (
            '<div class="hero-card">'
            f'<h1 style="margin: 0; font-size: 54px; font-weight: 900; color: #ffffff; letter-spacing: 1px;">¡Hola {nombre_show}!</h1>'
            f'<h2 style="color: {cat_show["color"]}; margin-top: 6px; font-size: 32px; font-weight: 900; text-shadow: 0 0 20px {cat_show["color"]}66;">Tu Score es {cat_show["label"].replace("Puntaje ", "")}</h2>'
            f'<div class="circle-container" style="border: 20px solid {cat_show["color"]}; box-shadow: 0 0 45px {cat_show["color"]}44;">'
            '<span style="color: #94a3b8; font-size: 18px; font-weight: 900;">Tu score es</span>'
            f'<span class="circle-score" style="color: {cat_show["color"]}; text-shadow: 0 0 25px {cat_show["color"]}88;">{score_show}</span>'
            '<span style="color: #94a3b8; font-size: 18px; font-weight: 900;">de 999</span>'
            '</div>'
            f'<h3 style="color: {cat_show["color"]}; font-weight: 900; font-size: 24px; margin: 4px 0 18px 0; letter-spacing: 1px;">● VERIFICADO POR BURÓ</h3>'
            '<div style="border-top: 2px solid #334155; padding-top: 18px; margin-top: 10px;">'
            '<div style="font-size: 15px; font-weight: 900; color: #94a3b8; letter-spacing: 1.5px; margin-bottom: 12px;">ESCALA DE RIESGO CREDITICIO</div>'
            '<div class="brick-container">'
            + html_ladrillos +
            '</div>'
            '</div>'
            '</div>'
        )
        st.markdown(card_bloques, unsafe_allow_html=True)

    # ==================== VISTA 2: NIVELES VERTICALES APILADOS ====================
    elif estilo_activo == "2. Niveles Verticales":
        html_barras = ""
        for r in RANGOS:
            es_act = (r["label"] == cat_show["label"])
            clase_s = "stacked-bar stacked-bar-active" if es_act else "stacked-bar"
            indicador = "  ◄" if es_act else ""
            html_barras += (
                f'<div class="{clase_s}" style="background-color: {r["color"]}; color: {r["texto_col"]} !important;">'
                f'<span style="font-size: 22px; font-weight: 900;">Score: {r["rango_texto"]}</span>'
                f'<span style="font-size: 20px; font-weight: 900;">{r["label"]}{indicador}</span>'
                f'</div>'
            )

        card_vertical = (
            '<div class="hero-card" style="text-align: left; padding: 30px 24px;">'
            f'<div style="text-align: center; border-bottom: 2px solid #334155; padding-bottom: 18px; margin-bottom: 20px;">'
            f'<h1 style="margin: 0; font-size: 50px; font-weight: 900; color: #ffffff;">¡Hola {nombre_show}!</h1>'
            f'<h2 style="color: {cat_show["color"]}; margin: 6px 0 0 0; font-size: 34px; font-weight: 900; text-shadow: 0 0 20px {cat_show["color"]}66;">{score_show} pts — {cat_show["label"]}</h2>'
            f'</div>'
            '<div style="font-size: 16px; font-weight: 900; color: #94a3b8; margin-bottom: 14px; text-align: center; letter-spacing: 1px;">TABLA OFICIAL DE CALIFICACIÓN SBS</div>'
            + html_barras +
            f'<div style="text-align: center; margin-top: 18px; font-size: 20px; font-weight: 900; color: {cat_show["color"]};">● VERIFICADO POR BURÓ PRIVADO</div>'
            '</div>'
        )
        st.markdown(card_vertical, unsafe_allow_html=True)

    # ==================== VISTA 3: DEUDAS BANCARIAS ====================
    elif estilo_activo == "3. Deudas Bancarias":
        total_soles = 0.0
        for d in deudas_show:
            try:
                total_soles += float(d["monto"].replace(",", ""))
            except:
                pass
        total_fmt = f"{total_soles:,.2f}"

        html_bancos = ""
        if deudas_show:
            for d in deudas_show:
                info_sbs = COLORES_SBS.get(d["calif"], COLORES_SBS["NOR"])
                dias_txt = "Al día (0 días)" if (d["dias"] == "0" or not d["dias"]) else f"{d['dias']} días atraso"
                html_bancos += (
                    '<div class="bank-card">'
                    '<div>'
                    f'<div style="font-size: 22px; font-weight: 900; color: #ffffff; margin-bottom: 4px;">🏦 {d["banco"]}</div>'
                    f'<div style="font-size: 15px; font-weight: 900; color: #94a3b8;">Deuda actual: <span style="font-size: 26px; font-weight: 900; color: #38bdf8;">S/ {d["monto"]}</span></div>'
                    '</div>'
                    f'<div class="bank-badge" style="background-color: {info_sbs["color"]}; color: {info_sbs["texto"]};">'
                    f'{info_sbs["nombre"]} • {dias_txt}'
                    '</div>'
                    '</div>'
                )
        else:
            html_bancos = (
                '<div style="background: #151e32; border: 2.5px dashed #334155; border-radius: 20px; padding: 40px; text-align: center;">'
                '<div style="font-size: 45px; margin-bottom: 8px;">✅</div>'
                '<h2 style="margin: 0; color: #00e676; font-weight: 900;">NO REGISTRA DEUDAS SBS</h2>'
                '<p style="color: #94a3b8; margin-top: 6px; font-size: 16px;">Deuda actual: S/ 0.00 en el sistema financiero.</p>'
                '</div>'
            )

        st.markdown(
            '<div style="max-width: 650px; margin: 0 auto;">'
            '<div class="total-deuda-banner">'
            '<div>'
            '<div style="font-size: 13px; color: #cbd5e1; font-weight: 900;">DEUDA SBS / MICROFINANZAS</div>'
            f'<div style="font-size: 28px; font-weight: 900; color: white;">{nombre_show}</div>'
            '</div>'
            '<div style="text-align: right;">'
            '<div style="font-size: 12px; color: #cbd5e1; font-weight: 900;">DEUDA TOTAL</div>'
            f'<div style="font-size: 36px; font-weight: 900; color: #38bdf8;">S/ {total_fmt}</div>'
            '</div>'
            '</div>'
            + html_bancos +
            '</div>',
            unsafe_allow_html=True
        )

    # ==================== VISTA 4: OTRAS DEUDAS ====================
    elif estilo_activo == "4. Otras Deudas":
        total_venc_soles = 0.0
        for v in vencidos_show:
            try:
                total_venc_soles += float(v["monto"].replace(",", ""))
            except:
                pass
        total_venc_fmt = f"{total_venc_soles:,.2f}"

        html_vencidos = ""
        if vencidos_show:
            for v in vencidos_show:
                dias_v = v["dias"]
                dias_v_txt = f"{dias_v} días vencido" if dias_v.isdigit() else "Impago"
                html_vencidos += (
                    '<div class="bank-card" style="border: 2.5px solid #ef4444;">'
                    '<div>'
                    f'<div style="font-size: 22px; font-weight: 900; color: #ffffff; margin-bottom: 4px;">⚠️ {v["acreedor"]}</div>'
                    f'<div style="font-size: 15px; font-weight: 900; color: #94a3b8;">Monto vencido: <span style="font-size: 26px; font-weight: 900; color: #ef4444;">S/ {v["monto"]}</span></div>'
                    '</div>'
                    '<div class="bank-badge" style="background-color: #ef4444; color: #ffffff;">'
                    f'VENCIDO • {dias_v_txt}'
                    '</div>'
                    '</div>'
                )
        else:
            html_vencidos = (
                '<div style="background: #151e32; border: 2.5px dashed #334155; border-radius: 20px; padding: 40px; text-align: center;">'
                '<div style="font-size: 45px; margin-bottom: 8px;">🛡️</div>'
                '<h2 style="margin: 0; color: #00e676; font-weight: 900;">SIN PROTESTOS NI VENCIDOS</h2>'
                '<p style="color: #94a3b8; margin-top: 6px; font-size: 16px;">No registra documentos impagos en cámara de comercio.</p>'
                '</div>'
            )

        st.markdown(
            '<div style="max-width: 650px; margin: 0 auto;">'
            '<div class="total-vencidos-banner">'
            '<div>'
            '<div style="font-size: 13px; color: #fca5a5; font-weight: 900;">OTRAS DEUDAS POR REGULARIZAR</div>'
            f'<div style="font-size: 28px; font-weight: 900; color: white;">{nombre_show}</div>'
            '</div>'
            '<div style="text-align: right;">'
            '<div style="font-size: 12px; color: #fca5a5; font-weight: 900;">TOTAL PENDIENTE</div>'
            f'<div style="font-size: 36px; font-weight: 900; color: #fef08a;">S/ {total_venc_fmt}</div>'
            '</div>'
            '</div>'
            + html_vencidos +
            '</div>',
            unsafe_allow_html=True
        )
