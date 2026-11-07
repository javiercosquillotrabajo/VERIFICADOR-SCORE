import streamlit as st
import streamlit.components.v1 as components
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

try:
    params = st.query_params
    es_pantalla_live = (params.get("live", "0") == "1")
except:
    es_pantalla_live = False

css_base = (
    "<style>"
    ".stApp { background-color: #cbd5e1; color: #0f172a; }"
    "h1, h2, h3, h4, h5, p, span { color: #0f172a; font-family: 'Segoe UI', Tahoma, sans-serif; }"
    ".card-panel { background: #ffffff; border: 2.5px solid #94a3b8; border-radius: 22px; padding: 26px; box-shadow: 0 12px 35px rgba(15,23,42,0.12); }"
    ".tier-card { padding: 16px 20px; border-radius: 14px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; font-weight: 900; font-size: 18px; color: #ffffff !important; opacity: 0.55; transition: all 0.25s ease; text-shadow: 0 1px 3px rgba(0,0,0,0.3); }"
    ".tier-active { opacity: 1 !important; transform: scale(1.05); box-shadow: 0 12px 30px rgba(0,0,0,0.3) !important; }"
    ".circle-container { width: 290px; height: 290px; border-radius: 50%; margin: 20px auto; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #ffffff; box-shadow: 0 15px 40px rgba(0,0,0,0.14); }"
    ".circle-score { font-size: 85px; font-weight: 900; line-height: 1; margin: 2px 0; }"
    ".loading-box { background: #ffffff; border: 3.5px solid #2563eb; border-radius: 24px; padding: 45px 30px; text-align: center; margin: 40px auto; max-width: 650px; box-shadow: 0 15px 40px rgba(15,23,42,0.15); }"
    ".bank-card { background: #ffffff; border: 2px solid #94a3b8; border-radius: 18px; padding: 20px 24px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 6px 20px rgba(15,23,42,0.06); }"
    ".bank-badge { padding: 10px 20px; border-radius: 25px; font-weight: 900; font-size: 15px; color: #ffffff; text-align: center; letter-spacing: 0.5px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }"
    ".total-deuda-banner { background: linear-gradient(135deg, #1e3a8a, #0f172a); border-radius: 20px; padding: 24px 30px; color: white; display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; box-shadow: 0 10px 30px rgba(30,58,138,0.25); border: 2px solid #3b82f6; }"
    ".cert-container { background: #ffffff; border: 2.5px solid #94a3b8; border-top: 12px solid #1e3a8a; border-radius: 18px; padding: 35px; max-width: 820px; margin: 0 auto; box-shadow: 0 15px 40px rgba(15,23,42,0.1); }"
    ".cert-score-box { background: #f8fafc; border: 3px dashed #94a3b8; border-radius: 18px; padding: 25px; text-align: center; margin: 20px 0; }"
    ".progress-bar-container { display: flex; height: 18px; border-radius: 9px; overflow: hidden; margin: 15px 0 6px 0; }"
    "div[data-testid='stRadio'] > div { justify-content: center; gap: 15px; background: #ffffff; padding: 10px 18px; border-radius: 30px; border: 2px solid #94a3b8; box-shadow: 0 4px 15px rgba(0,0,0,0.06); }"
    "</style>"
)
st.markdown(css_base, unsafe_allow_html=True)

RANGOS = [
    {"label": "Excelente Puntaje", "min": 877, "max": 999, "color": "#00c853", "rango_texto": "877 - 999", "prob_prestamo": "Alta (Preferencial)", "tarjetas": "Líneas altas", "riesgo": "Mínimo"},
    {"label": "Buen Puntaje",      "min": 722, "max": 876, "color": "#00e676", "rango_texto": "722 - 876", "prob_prestamo": "Alta", "tarjetas": "Aprobación Rápida", "riesgo": "Bajo"},
    {"label": "Puntaje Medio",     "min": 598, "max": 721, "color": "#ffb300", "rango_texto": "598 - 721", "prob_prestamo": "Media (Evaluación)", "tarjetas": "Límites moderados", "riesgo": "Moderado"},
    {"label": "Puntaje Bajo",      "min": 477, "max": 597, "color": "#ff6d00", "rango_texto": "477 - 597", "prob_prestamo": "Baja", "tarjetas": "Con garantía / aval", "riesgo": "Alto"},
    {"label": "Puntaje Muy Bajo",  "min": 0,   "max": 476, "color": "#ff1744", "rango_texto": "0 - 476",   "prob_prestamo": "No Apto", "tarjetas": "Restringidas", "riesgo": "Crítico"},
]

COLORES_SBS = {
    "NOR": {"nombre": "NORMAL", "color": "#00c853"},
    "CPP": {"nombre": "CPP", "color": "#ffb300"},
    "DEF": {"nombre": "DEFICIENTE", "color": "#ff6d00"},
    "DUD": {"nombre": "DUDOSO", "color": "#ff1744"},
    "PER": {"nombre": "PÉRDIDA", "color": "#ff1744"},
    "SCAL": {"nombre": "SIN CALIF.", "color": "#94a3b8"}
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
    """Extrae las deudas por banco buscando específicamente en la página con la tabla de Entidad."""
    deudas = []

    for pag in pdf.pages:
        txt = pag.extract_text() or ""
        # Debe ser la página que contiene la tabla real con "Entidad" y montos anteriores
        if not ("Entidad" in txt and ("Deuda Anterior" in txt or "SET 2026" in txt or "JUL 2026" in txt or "ABR 2026" in txt or "Fecha Inf" in txt)):
            continue

        lineas = txt.splitlines()
        en_tabla = False

        for l in lineas:
            l_strip = l.strip()
            if "Detalle de la deuda SBS" in l_strip or "Entidad" in l_strip:
                en_tabla = True
                continue

            if en_tabla:
                if "TOTAL" in l_strip.upper() or "Detalle de vencidos" in l_strip or "Utilización de Líneas" in l_strip or "Otros documentos" in l_strip:
                    en_tabla = False
                    break

                if not l_strip:
                    continue

                # Busca calificación SBS (NOR, CPP, DEF, DUD, PER, SCAL)
                m_calif = re.search(r"\b(NOR|CPP|DEF|DUD|PER|SCAL)\b", l_strip)
                if m_calif:
                    calif = m_calif.group(1).upper()
                    pos_calif = m_calif.start()

                    parte_izq = l_strip[:pos_calif].strip()
                    parte_der = l_strip[m_calif.end():].strip()

                    # Nombre del banco antes del primer decimal o fecha
                    m_banco = re.search(r"^([A-ZÁÉÍÓÚÑa-záéíóúñ\s\.\/\-\&]+?)(?=\s+[\d,]+\.\d{2}|\s+\d{2}\/\d{2}\/\d{4})", parte_izq)
                    if m_banco:
                        nombre_banco = m_banco.group(1).strip()
                    else:
                        palabras = parte_izq.split()
                        nombre_banco = " ".join([p for p in palabras if not re.search(r"\d", p)])

                    if not nombre_banco or "ENTIDAD" in nombre_banco.upper():
                        continue

                    # Monto del último mes
                    m_monto = re.search(r"([\d,]+\.\d{2})", parte_der)
                    if m_monto:
                        monto = m_monto.group(1)
                        resto = parte_der[m_monto.end():].strip()
                        m_dias = re.search(r"\b(\d{1,4})\b", resto)
                        dias = m_dias.group(1) if m_dias else "0"
                    else:
                        todos = re.findall(r"[\d,]+\.\d{2}", l_strip)
                        monto = todos[-1] if todos else "0.00"
                        dias = "0"

                    deudas.append({
                        "banco": nombre_banco,
                        "monto": monto,
                        "calif": calif,
                        "dias": dias
                    })

        if deudas:
            break

    return deudas

def generar_pdf_descarga(nombre, score, categoria):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4

    c.setFillColor(colors.HexColor("#cbd5e1"))
    c.rect(0, 0, ancho, alto, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, alto - 50, "VERIFICACIÓN DE SCORE CREDITICIO")

    c.setStrokeColor(colors.HexColor("#94a3b8"))
    c.setLineWidth(1.5)
    c.line(50, alto - 60, ancho - 50, alto - 60)

    c.setFillColor(colors.white)
    c.setStrokeColor(colors.HexColor(categoria["color"]))
    c.setLineWidth(2.5)
    c.roundRect(50, alto - 280, ancho - 100, 200, 15, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 24)
    c.drawString(75, alto - 110, f"¡HOLA, {nombre}!")

    c.setFont("Helvetica-Bold", 15)
    c.setFillColor(colors.HexColor(categoria["color"]))
    c.drawString(75, alto - 138, f"Tu Score es {categoria['label'].replace('Puntaje ', '')}")

    cx = ancho - 150
    cy = alto - 180
    c.setStrokeColor(colors.HexColor(categoria["color"]))
    c.setLineWidth(9)
    c.setFillColor(colors.white)
    c.circle(cx, cy, 58, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#64748b"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(cx, cy + 26, "Tu score es")

    c.setFillColor(colors.HexColor(categoria["color"]))
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(cx, cy - 10, str(score))

    c.setFillColor(colors.HexColor("#64748b"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(cx, cy - 26, "de 999")

    c.setFillColor(colors.HexColor(categoria["color"]))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(75, alto - 195, f"● Rango: {categoria['rango_texto']}")
    c.drawString(75, alto - 222, "● Estado: VERIFICADO")

    y_tabla = alto - 320
    for r in RANGOS:
        es_activo = (r["label"] == categoria["label"])
        bg = colors.HexColor(r["color"]) if es_activo else colors.white
        borde = colors.HexColor(r["color"]) if es_activo else colors.HexColor("#cbd5e1")

        c.setFillColor(bg)
        c.setStrokeColor(borde)
        c.setLineWidth(2 if es_activo else 1)
        c.roundRect(50, y_tabla - 18, ancho - 100, 24, 6, fill=1, stroke=1)

        c.setFillColor(colors.white
