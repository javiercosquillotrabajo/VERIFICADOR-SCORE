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

# Leer parámetros
try:
    params = st.query_params
    es_pantalla_live = (params.get("live", "0") == "1")
except:
    es_pantalla_live = False

# ESTILOS EN TEMA CLARO ELEGANTE
css_claro = (
    "<style>"
    ".stApp { background-color: #f1f5f9; color: #0f172a; }"
    "h1, h2, h3, h4, h5, p, span { color: #0f172a; font-family: 'Segoe UI', sans-serif; }"
    ".card-panel { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 18px; padding: 25px; box-shadow: 0 6px 20px rgba(0,0,0,0.05); }"
    ".tier-card { padding: 14px 18px; border-radius: 12px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; font-weight: 700; font-size: 15px; color: #ffffff !important; opacity: 0.35; transition: all 0.3s ease; }"
    ".tier-active { opacity: 1 !important; transform: scale(1.03); box-shadow: 0 8px 25px rgba(0,0,0,0.2) !important; }"
    ".circle-container { width: 250px; height: 250px; border-radius: 50%; margin: 25px auto; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #ffffff; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }"
    ".circle-score { font-size: 68px; font-weight: 900; line-height: 1; margin: 5px 0; color: #0f172a; }"
    ".loading-box { background: #ffffff; border: 2px solid #2563eb; border-radius: 20px; padding: 35px 25px; text-align: center; margin: 40px auto; max-width: 620px; box-shadow: 0 10px 35px rgba(37,99,235,0.15); }"
    ".btn-live-link { display: inline-block; width: 100%; background: linear-gradient(90deg, #2563eb, #059669); color: white !important; text-align: center; padding: 16px 20px; font-size: 16px; font-weight: 800; border-radius: 12px; text-decoration: none; box-shadow: 0 4px 15px rgba(37,99,235,0.25); margin-top: 15px; }"
    "</style>"
)
st.markdown(css_claro, unsafe_allow_html=True)

RANGOS = [
    {"label": "Excelente Puntaje", "min": 877, "max": 999, "color": "#059669", "rango_texto": "877 - 999"},
    {"label": "Buen Puntaje",      "min": 722, "max": 876, "color": "#10b981", "rango_texto": "722 - 876"},
    {"label": "Puntaje Medio",     "min": 598, "max": 721, "color": "#f59e0b", "rango_texto": "598 - 721"},
    {"label": "Puntaje Bajo",      "min": 477, "max": 597, "color": "#ea580c", "rango_texto": "477 - 597"},
    {"label": "Puntaje Muy Bajo",  "min": 0,   "max": 476, "color": "#dc2626", "rango_texto": "0 - 476"},
]

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

def generar_pdf_descarga(nombre, score, categoria):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4

    c.setFillColor(colors.white)
    c.rect(0, 0, ancho, alto, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, alto - 50, "VERIFICACIÓN DE SCORE CREDITICIO")

    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.setLineWidth(1)
    c.line(50, alto - 60, ancho - 50, alto - 60)

    # Recuadro Principal
    c.setFillColor(colors.HexColor("#f8fafc"))
    c.setStrokeColor(colors.HexColor(categoria["color"]))
    c.setLineWidth(2)
    c.roundRect(50, alto - 280, ancho - 100, 200, 15, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(75, alto - 110, f"¡HOLA, {nombre}!")

    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor(categoria["color"]))
    c.drawString(75, alto - 135, f"Tu Score es {categoria['label'].replace('Puntaje ', '')}")

    cx = ancho - 150
    cy = alto - 180
    c.setStrokeColor(colors.HexColor(categoria["color"]))
    c.setLineWidth(8)
    c.setFillColor(colors.white)
    c.circle(cx, cy, 55, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#64748b"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx, cy + 25, "Tu score es")

    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(cx, cy - 8, str(score))

    c.setFillColor(colors.HexColor("#64748b"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx, cy - 23, "de 999")

    c.setFillColor(colors.HexColor(categoria["color"]))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(75, alto - 195, f"● Rango: {categoria['rango_texto']}")
    c.drawString(75, alto - 220, "● Estado: VERIFICADO")

    # Escala SBS
    y_tabla = alto - 320
    for r in RANGOS:
        es_activo = (r["label"] == categoria["label"])
        bg = colors.HexColor(r["color"]) if es_activo else colors.HexColor("#f1f5f9")
        borde = colors.HexColor(r["color"]) if es_activo else colors.HexColor("#e2e8f0")

        c.setFillColor(bg)
        c.setStrokeColor(borde)
        c.setLineWidth(1.5 if es_activo else 0.5)
        c.roundRect(50, y_tabla - 18, ancho - 100, 24, 4, fill=1, stroke=1)

        c.setFillColor(colors.white if es_activo else colors.HexColor("#334155"))
        c.setFont("Helvetica-Bold" if es_activo else "Helvetica", 9)
        c.drawString(65, y_tabla - 12, f"Score: {r['rango_texto']}")
        c.drawRightString(ancho - 65, y_tabla - 12, r["label"])

        y_tabla -= 28

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# =========================================================================
# VISTA 1: PESTAÑA PROYECTORA DEL LIVE (100% LIMPIA EN COLOR CLARO)
# =========================================================================
if es_pantalla_live:
    css_limpio = (
        "<style>"
        "[data-testid='stSidebar'] { display: none !important; }"
        "header { display: none !important; }"
        "#MainMenu { display: none !important; }"
        "footer { display: none !important; }"
        ".block-container { padding-top: 1.5rem !important; max-width: 950px !important; }"
        "</style>"
    )
    st.markdown(css_limpio, unsafe_allow_html=True)

    nombre_live = params.get("nombre", "CLIENTE")
    try:
        score_live = int(params.get("score", "0"))
    except:
        score_live = 0
    t_stamp = params.get("t", "0")

    key_anim = f"animada_{t_stamp}"
    if key_anim not in st.session_state:
        anim_ph = st.empty()
        pasos = [
            (25, "🔍 Conectando con bases de datos SBS y Buró...", "📡 Verificando documento oficial..."),
            (60, "📊 Analizando historial de pagos y deudas...", "📂 Procesando líneas de crédito..."),
            (90, "⚙️ Verificando niveles de riesgo y morosidad...", "🛡️ Contrastando semáforo financiero..."),
            (100, "¡EVALUACIÓN COMPLETADA!", "● Mostrando resultado oficial...")
        ]
        for pct, tit, sub in pasos:
            caja_anim = (
                '<div class="loading-box">'
                '<div style="font-size: 45px; margin-bottom: 12px;">🛰️</div>'
                '<h2 style="color: #2563eb; margin: 0; font-weight: 800;">CONSULTANDO CENTRAL DE RIESGOS</h2>'
                f'<h4 style="color: #0f172a; margin: 15px 0 5px 0;">{tit}</h4>'
                f'<p style="color: #64748b; font-size: 13px; margin-bottom: 20px;">{sub}</p>'
                '<div style="background: #e2e8f0; height: 14px; border-radius: 7px; overflow: hidden;">'
                f'<div style="background: linear-gradient(90deg, #2563eb, #10b981); width: {pct}%; height: 100%; border-radius: 7px;"></div>'
                '</div>'
                f'<p style="color: #64748b; font-size: 12px; margin-top: 8px;">Progreso: {pct}%</p>'
                '</div>'
            )
            anim_ph.markdown(caja_anim, unsafe_allow_html=True)
            time.sleep(0.35)
        anim_ph.empty()
        st.session_state[key_anim] = True

    categoria = clasificar_score(score_live)

    col_izq, col_der = st.columns([1, 1], gap="large")
    with col_izq:
        st.markdown("<div class='card-panel'>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:0;'>Score Crediticio</h3>", unsafe_allow_html=True)
        st.caption("Es un número que indica la probabilidad de cumplir con tus obligaciones financieras.")
        st.write("")
        for r in RANGOS:
            activo = (r["label"] == categoria["label"])
            clase = "tier-active" if activo else ""
            borde = f"border: 2.5px solid {r['color']};" if activo else "border: 1px solid #cbd5e1;"
            html_card = (
                f'<div class="tier-card {clase}" style="background-color: {r["color"]}; {borde}">'
                f'<span>Score: {r["rango_texto"]}</span>'
                f'<span>{r["label"]}</span>'
                '</div>'
            )
            st.markdown(html_card, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_der:
        st.markdown("<div class='card-panel' style='text-align: center;'>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='margin: 0; font-size: 42px;'>¡Hola {nombre_live}!</h1>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color: {categoria['color']}; margin-top: 5px; font-weight: 800;'>Tu Score es {categoria['label'].replace('Puntaje ', '')}</h2>", unsafe_allow_html=True)
        html_circle = (
            f'<div class="circle-container" style="border: 15px solid {categoria["color"]};">'
            '<span style="color: #64748b; font-size: 16px; font-weight: 600;">Tu score es</span>'
            f'<span class="circle-score">{score_live}</span>'
            '<span style="color: #64748b; font-size: 16px; font-weight: 600;">de 999</span>'
            '</div>'
        )
        st.markdown(html_circle, unsafe_allow_html=True)
        st.markdown(f"<h4 style='color: {categoria['color']}; font-weight: 800;'>● Verificado</h4>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()


# =========================================================================
# VISTA 2: TU PANEL DE CONTROL PRIVADO (TEMA CLARO)
# =========================================================================
st.markdown("<h1 style='text-align: center;'>🎛️ PANEL DE CONTROL (PRIVADO)</h1>", unsafe_allow_html=True)
st.caption("Esta pestaña es solo para ti. Tus seguidores verán la pestaña nueva proyectada en el Live.")

uploaded_file = st.file_uploader("📂 Sube aquí el PDF del reporte", type=["pdf"])

detected_nombre = "CLIENTE"
detected_score = 0

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        s = extraer_score_experian(pdf.pages[0])
        n = extraer_nombre(pdf)
        if s is not None:
            detected_score = s
        if n:
            detected_nombre = n

col_c1, col_c2 = st.columns(2)
with col_c1:
    nombre_final = st.text_input("Nombre detectado (editable):", value=detected_nombre)
with col_c2:
    score_input = st.number_input("Score detectado (editable):", min_value=0, max_value=999, value=detected_score)

score_val = 0 if score_input == 92 else score_input

# Enlace mágico que abre y actualiza la MISMA pestaña del Live
nombre_encoded = urllib.parse.quote(nombre_final)
t_now = int(time.time())
url_live = f"?live=1&nombre={nombre_encoded}&score={score_val}&t={t_now}"

boton_html = (
    f'<a href="{url_live}" target="pantalla_live" class="btn-live-link">'
    f'🚀 ABRIR / ACTUALIZAR EN PESTAÑA DEL LIVE'
    f'</a>'
)
st.markdown(boton_html, unsafe_allow_html=True)

st.markdown("---")
cat_priv = clasificar_score(score_val)
pdf_bytes = generar_pdf_descarga(nombre_final, score_val, cat_priv)
st.download_button(
    label="📥 Guardar PDF descargable",
    data=pdf_bytes,
    file_name=f"Score_{nombre_final}_{score_val}.pdf",
    mime="application/pdf"
)
