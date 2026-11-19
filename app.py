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
    "  border: 2px solid #334155;"
    "  border-radius: 24px;"
    "  padding: 26px 20px;"
    "  box-shadow: 0 15px 45px rgba(0,0,0,0.5);"
    "}"
    "div[data-testid='stTextInput'] input, div[data-testid='stNumberInput'] input {"
    "  font-size: 26px !important; font-weight: 900 !important; height: 64px !important; color: #ffffff !important; background-color: #0f172a !important; border: 2.5px solid #475569 !important; border-radius: 16px !important; padding: 12px 18px !important;"
    "}"
    "div[data-testid='stTextInput'] label, div[data-testid='stNumberInput'] label {"
    "  font-size: 22px !important; font-weight: 900 !important; color: #38bdf8 !important; margin-bottom: 8px !important;"
    "}"
    "div[data-testid='stButton'] button {"
    "  font-size: 21px !important; font-weight: 900 !important; padding: 18px 14px !important; border-radius: 16px !important; margin-top: 10px !important;"
    "}"
    ".speedometer-card { background: #151e32; border: 2px solid #334155; border-radius: 22px; padding: 24px 18px; margin: 12px auto; max-width: 620px; box-shadow: 0 15px 40px rgba(0,0,0,0.4); text-align: center; }"
    ".bank-card { background: #151e32; border: 2px solid #334155; border-radius: 16px; padding: 16px 20px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 8px 25px rgba(0,0,0,0.3); text-align: left; }"
    ".bank-badge { padding: 8px 16px; border-radius: 20px; font-weight: 900; font-size: 14px; color: #ffffff; text-align: center; }"
    ".total-deuda-banner { background: linear-gradient(135deg, #1e40af, #0f172a); border-radius: 18px; padding: 18px 24px; color: white; display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; border: 2px solid #38bdf8; }"
    ".total-vencidos-banner { background: linear-gradient(135deg, #b91c1c, #450a0a); border-radius: 18px; padding: 18px 24px; color: white; display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; border: 2px solid #f87171; }"
    "@keyframes agujaOscilar {"
    "  0% { transform: rotate(-65deg); }"
    "  25% { transform: rotate(15deg); }"
    "  50% { transform: rotate(65deg); }"
    "  75% { transform: rotate(-20deg); }"
    "  100% { transform: rotate(-65deg); }"
    "}"
    ".needle-anim { animation: agujaOscilar 2s ease-in-out infinite; transform-origin: 200px 180px; }"
    ".needle-locked { transform-origin: 200px 180px; transition: transform 1.2s cubic-bezier(0.175, 0.885, 0.32, 1.275); }"
    "div[data-testid='stRadio'] > div { justify-content: center; gap: 8px; background: #151e32; padding: 8px 14px; border-radius: 30px; border: 2px solid #334155; }"
    "div[data-testid='stRadio'] label span { font-weight: 900 !important; font-size: 13px !important; color: #f8fafc !important; }"
    "</style>"
)
st.markdown(css_base, unsafe_allow_html=True)

RANGOS = [
    {"label": "Excelente Puntaje", "min": 877, "max": 999, "color": "#00a650", "angle": -58, "sbs": "Normal"},
    {"label": "Buen Puntaje",      "min": 722, "max": 876, "color": "#8dc63f", "angle": -28, "sbs": "Problemas potenciales"},
    {"label": "Puntaje Medio",     "min": 598, "max": 721, "color": "#ffcc00", "angle": 0,   "sbs": "Deficiente"},
    {"label": "Puntaje Bajo",      "min": 477, "max": 597, "color": "#f37023", "angle": 28,  "sbs": "Dudoso"},
    {"label": "Puntaje Muy Bajo",  "min": 0,   "max": 476, "color": "#ed1c24", "angle": 58,  "sbs": "Pérdida"},
]

COLORES_SBS = {
    "NOR": {"nombre": "NORMAL", "color": "#00a650"},
    "CPP": {"nombre": "CPP", "color": "#ffcc00"},
    "DEF": {"nombre": "DEFICIENTE", "color": "#f37023"},
    "DUD": {"nombre": "DUDOSO", "color": "#ed1c24"},
    "PER": {"nombre": "PÉRDIDA", "color": "#ed1c24"},
    "SCAL": {"nombre": "SIN CALIF.", "color": "#64748b"}
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

                    # Filtrar si el acreedor es solo una fecha (ej: 20/10/2026) o si el monto es 0.00
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

def generar_svg_velocimetro(angulo, esta_oscilando):
    clase_aguja = "needle-anim" if esta_oscilando else "needle-locked"
    estilo_rot = "" if esta_oscilando else f"transform: rotate({angulo}deg);"
    svg = (
        '<svg viewBox="0 0 400 220" width="100%" style="max-width: 440px; margin: 0 auto; display: block;">'
        '<defs>'
        '<filter id="glow"><feGaussianBlur stdDeviation="3" result="coloredBlur"/><feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '</defs>'
        '<path d="M 50 180 A 150 150 0 0 1 93.9 74" fill="none" stroke="#00a650" stroke-width="36"/>'
        '<path d="M 93.9 74 A 150 150 0 0 1 163.5 32" fill="none" stroke="#8dc63f" stroke-width="36"/>'
        '<path d="M 163.5 32 A 150 150 0 0 1 236.5 32" fill="none" stroke="#ffcc00" stroke-width="36"/>'
        '<path d="M 236.5 32 A 150 150 0 0 1 306.1 74" fill="none" stroke="#f37023" stroke-width="36"/>'
        '<path d="M 306.1 74 A 150 150 0 0 1 350 180" fill="none" stroke="#ed1c24" stroke-width="36"/>'
        '<text x="42" y="196" fill="#94a3b8" font-size="12" font-weight="bold">Normal</text>'
        '<text x="70" y="48" fill="#94a3b8" font-size="11" font-weight="bold">Problemas</text>'
        '<text x="70" y="60" fill="#94a3b8" font-size="11" font-weight="bold">potenciales</text>'
        '<text x="175" y="20" fill="#94a3b8" font-size="12" font-weight="bold">Deficiente</text>'
        '<text x="295" y="55" fill="#94a3b8" font-size="12" font-weight="bold">Dudoso</text>'
        '<text x="325" y="196" fill="#94a3b8" font-size="12" font-weight="bold">Pérdida</text>'
        f'<g class="{clase_aguja}" style="{estilo_rot}">'
        '<polygon points="200,45 194,180 206,180" fill="#cbd5e1" filter="url(#glow)"/>'
        '<circle cx="200" cy="180" r="16" fill="#475569"/>'
        '<circle cx="200" cy="180" r="8" fill="#38bdf8"/>'
        '</g>'
        '<text x="200" y="215" fill="#38bdf8" font-size="14" font-weight="900" text-anchor="middle" letter-spacing="1">CATEGORÍAS DE RIESGO</text>'
        '</svg>'
    )
    return svg

# Inicialización de estados
if "live_nombre" not in st.session_state:
    st.session_state["live_nombre"] = "CLIENTE"
if "live_score" not in st.session_state:
    st.session_state["live_score"] = 650
if "live_deudas" not in st.session_state:
    st.session_state["live_deudas"] = []
if "live_vencidos" not in st.session_state:
    st.session_state["live_vencidos"] = []
if "modo_suspenso" not in st.session_state:
    st.session_state["modo_suspenso"] = False

# =========================================================================
# DISTRIBUCIÓN: COLUMNA IZQUIERDA (PANEL PRIVADO) vs COLUMNA DERECHA (LIVE)
# =========================================================================
col_panel, col_display = st.columns([1.1, 2.3], gap="large")

# =========================================================================
# 🎛️ LADO IZQUIERDO: PANEL DE CONTROL ESPACIOSO (SIN CUADRO FANTASMA)
# =========================================================================
with col_panel:
    st.markdown("<h2 style='margin:0 0 4px 0; color:#38bdf8; font-size:28px; font-weight:900;'>🎛️ PANEL PRIVADO</h2>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:15px; color:#94a3b8; font-weight:bold; margin-bottom:18px;'>Consola de control (fuera de cámara).</p>", unsafe_allow_html=True)

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

    st.markdown("<div style='margin-top:22px;'></div>", unsafe_allow_html=True)
    if st.button("🚀 TRANSMITIR EN VIVO", use_container_width=True, type="primary"):
        st.session_state["live_nombre"] = nombre_ctrl
        st.session_state["live_score"] = score_final_ctrl
        st.session_state["live_deudas"] = detected_deudas
        st.session_state["live_vencidos"] = detected_vencidos
        st.session_state["modo_suspenso"] = False
        st.rerun()

    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
    if st.button("🎭 ACTIVAR SUSPENSO (OSCILAR)", use_container_width=True):
        st.session_state["live_nombre"] = nombre_ctrl
        st.session_state["live_score"] = score_final_ctrl
        st.session_state["live_deudas"] = detected_deudas
        st.session_state["live_vencidos"] = detected_vencidos
        st.session_state["modo_suspenso"] = True
        st.rerun()

    st.markdown("<hr style='border-color:#334155; margin:24px 0;'>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:#0f172a; border:2px solid #334155; border-radius:16px; padding:16px 18px; margin-bottom:12px;'>"
        f"<div style='font-size:16px; font-weight:900; color:#00e676; margin-bottom:4px;'>🏦 DEUDAS SBS:</div>"
        f"<div style='font-size:22px; font-weight:900; color:#ffffff;'>{len(detected_deudas)} detectadas</div>"
        f"</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        f"<div style='background:#0f172a; border:2px solid #334155; border-radius:16px; padding:16px 18px;'>"
        f"<div style='font-size:16px; font-weight:900; color:#f87171; margin-bottom:4px;'>⚠️ OTRAS DEUDAS:</div>"
        f"<div style='font-size:22px; font-weight:900; color:#ffffff;'>{len(detected_vencidos)} detectadas</div>"
        f"</div>",
        unsafe_allow_html=True
    )

# =========================================================================
# 📺 LADO DERECHO: PANTALLA EN VIVO (LO QUE CAPTURA TIKTOK STUDIO)
# =========================================================================
with col_display:
    nombre_show = st.session_state["live_nombre"]
    score_show = st.session_state["live_score"]
    deudas_show = st.session_state["live_deudas"]
    vencidos_show = st.session_state["live_vencidos"]
    suspenso = st.session_state["modo_suspenso"]

    cat_show = clasificar_score(score_show)

    estilo_sel = st.radio(
        "Navegación:",
        ["1. Velocímetro SBS", "2. Ficha y Pastillas", "3. Deudas Bancarias", "4. Otras Deudas"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.write("")

    # ==================== VISTA 1: VELOCÍMETRO SBS CON AGUJA ====================
    if estilo_sel == "1. Velocímetro SBS":
        svg_gauge = generar_svg_velocimetro(cat_show["angle"], suspenso)
        texto_estado = "● OSCILANDO - EVALUANDO RIESGO EN VIVO..." if suspenso else f"● {cat_show['label'].upper()} ({cat_show['sbs']})"
        color_estado = "#ffcc00" if suspenso else cat_show["color"]

        card_velocimetro = (
            '<div class="speedometer-card">'
            f'<h1 style="margin: 0; font-size: 48px; font-weight: 900; color: #ffffff;">¡Hola {nombre_show}!</h1>'
            f'<h3 style="color: {color_estado}; margin: 6px 0 14px 0; font-size: 24px; font-weight: 900;">{texto_estado}</h3>'
            + svg_gauge +
            f'<div style="background: #0f172a; border: 2.5px solid {cat_show["color"]}; border-radius: 18px; padding: 14px 20px; display: inline-block; margin-top: 15px; box-shadow: 0 0 25px {cat_show["color"]}44;">'
            f'<span style="font-size: 14px; color: #94a3b8; font-weight: 800; display: block;">SCORE ASIGNADO</span>'
            f'<span style="font-size: 64px; font-weight: 900; color: {cat_show["color"]}; line-height: 1;">{score_show}</span>'
            f'<span style="font-size: 14px; color: #94a3b8; font-weight: 800;"> / 999 pts</span>'
            f'</div>'
            '</div>'
        )
        st.markdown(card_velocimetro, unsafe_allow_html=True)

    # ==================== VISTA 2: FICHA Y PASTILLAS ====================
    elif estilo_sel == "2. Ficha y Pastillas":
        html_pills = ""
        for r in RANGOS:
            es_act = (r["label"] == cat_show["label"])
            opacidad = "1 !important; transform: scale(1.08); border: 2.5px solid #ffffff;" if es_act else "0.35;"
            html_pills += f'<div style="flex:1; padding: 10px 4px; border-radius: 10px; font-size: 12px; font-weight: 900; background:{r["color"]}; color:{r["color"]}; opacity:{opacidad}; text-align:center;">{r["sbs"]}</div>'

        card_ficha = (
            '<div class="speedometer-card">'
            f'<h1 style="margin: 0; font-size: 48px; font-weight: 900; color: #ffffff;">¡Hola {nombre_show}!</h1>'
            f'<h2 style="color: {cat_show["color"]}; margin-top: 6px; font-size: 28px; font-weight: 900;">Tu Score es {cat_show["label"].replace("Puntaje ", "")}</h2>'
            f'<div style="width: 210px; height: 210px; border-radius: 50%; margin: 15px auto; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #0f172a; border: 16px solid {cat_show["color"]}; box-shadow: 0 0 35px {cat_show["color"]}44;">'
            f'<span style="color: #94a3b8; font-size: 14px; font-weight: 800;">Tu score es</span>'
            f'<span style="font-size: 72px; font-weight: 900; color: {cat_show["color"]}; line-height:1;">{score_show}</span>'
            f'<span style="color: #94a3b8; font-size: 14px; font-weight: 800;">de 999</span>'
            f'</div>'
            f'<h3 style="color: {cat_show["color"]}; font-weight: 900; font-size: 20px; margin: 4px 0 14px 0;">● VERIFICADO POR BURÓ</h3>'
            '<div style="border-top: 2px solid #334155; padding-top: 14px;">'
            '<div style="font-size: 12px; font-weight: 900; color: #94a3b8; letter-spacing: 1px; margin-bottom: 8px;">NIVELES DE CALIFICACIÓN SBS</div>'
            '<div style="display: flex; gap: 6px; justify-content: space-between;">'
            + html_pills +
            '</div>'
            '</div>'
            '</div>'
        )
        st.markdown(card_ficha, unsafe_allow_html=True)

    # ==================== VISTA 3: DEUDAS BANCARIAS ====================
    elif estilo_sel == "3. Deudas Bancarias":
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
                    f'<div style="font-size: 20px; font-weight: 900; color: #ffffff; margin-bottom: 4px;">🏦 {d["banco"]}</div>'
                    f'<div style="font-size: 14px; font-weight: 800; color: #94a3b8;">Deuda actual: <span style="font-size: 24px; font-weight: 900; color: #38bdf8;">S/ {d["monto"]}</span></div>'
                    '</div>'
                    f'<div class="bank-badge" style="background-color: {info_sbs["color"]};">'
                    f'{info_sbs["nombre"]} • {dias_txt}'
                    '</div>'
                    '</div>'
                )
        else:
            html_bancos = (
                '<div style="background: #151e32; border: 2.5px dashed #334155; border-radius: 20px; padding: 40px; text-align: center;">'
                '<div style="font-size: 40px; margin-bottom: 8px;">✅</div>'
                '<h2 style="margin: 0; color: #00a650; font-weight: 900;">NO REGISTRA DEUDAS SBS</h2>'
                '<p style="color: #94a3b8; margin-top: 6px; font-size: 15px;">Deuda actual: S/ 0.00 en el sistema financiero.</p>'
                '</div>'
            )

        st.markdown(
            '<div style="max-width: 620px; margin: 0 auto;">'
            '<div class="total-deuda-banner">'
            '<div>'
            '<div style="font-size: 12px; color: #cbd5e1; font-weight: 900;">DEUDA SBS / MICROFINANZAS</div>'
            f'<div style="font-size: 26px; font-weight: 900; color: white;">{nombre_show}</div>'
            '</div>'
            '<div style="text-align: right;">'
            '<div style="font-size: 11px; color: #cbd5e1; font-weight: 900;">DEUDA TOTAL</div>'
            f'<div style="font-size: 32px; font-weight: 900; color: #38bdf8;">S/ {total_fmt}</div>'
            '</div>'
            '</div>'
            + html_bancos +
            '</div>',
            unsafe_allow_html=True
        )

    # ==================== VISTA 4: OTRAS DEUDAS ====================
    elif estilo_sel == "4. Otras Deudas":
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
                    '<div class="bank-card" style="border: 2px solid #ed1c24;">'
                    '<div>'
                    f'<div style="font-size: 20px; font-weight: 900; color: #ffffff; margin-bottom: 4px;">⚠️ {v["acreedor"]}</div>'
                    f'<div style="font-size: 14px; font-weight: 800; color: #94a3b8;">Monto vencido: <span style="font-size: 24px; font-weight: 900; color: #ed1c24;">S/ {v["monto"]}</span></div>'
                    '</div>'
                    '<div class="bank-badge" style="background-color: #ed1c24;">'
                    f'VENCIDO • {dias_v_txt}'
                    '</div>'
                    '</div>'
                )
        else:
            html_vencidos = (
                '<div style="background: #151e32; border: 2.5px dashed #334155; border-radius: 20px; padding: 40px; text-align: center;">'
                '<div style="font-size: 40px; margin-bottom: 8px;">🛡️</div>'
                '<h2 style="margin: 0; color: #00a650; font-weight: 900;">SIN PROTESTOS NI VENCIDOS</h2>'
                '<p style="color: #94a3b8; margin-top: 6px; font-size: 15px;">No registra documentos impagos en cámara de comercio.</p>'
                '</div>'
            )

        st.markdown(
            '<div style="max-width: 620px; margin: 0 auto;">'
            '<div class="total-vencidos-banner">'
            '<div>'
            '<div style="font-size: 12px; color: #fca5a5; font-weight: 900;">OTRAS DEUDAS POR REGULARIZAR</div>'
            f'<div style="font-size: 26px; font-weight: 900; color: white;">{nombre_show}</div>'
            '</div>'
            '<div style="text-align: right;">'
            '<div style="font-size: 11px; color: #fca5a5; font-weight: 900;">TOTAL PENDIENTE</div>'
            f'<div style="font-size: 32px; font-weight: 900; color: #fef08a;">S/ {total_venc_fmt}</div>'
            '</div>'
            '</div>'
            + html_vencidos +
            '</div>',
            unsafe_allow_html=True
        )
