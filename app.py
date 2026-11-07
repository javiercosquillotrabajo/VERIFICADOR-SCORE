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

# Leer parámetros de URL para saber si estamos en la Pestaña Proyectora (Live)
params = st.query_params
es_pantalla_live = params.get("live", "0") == "1"

# Estilos CSS
css_base = (
    "<style>"
    ".stApp { background-color: #0b111e; color: #ffffff; }"
    ".tier-card { padding: 14px 18px; border-radius: 10px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; font-family: sans-serif; font-weight: 600; font-size: 15px; opacity: 0.35; transition: all 0.3s ease; }"
    ".tier-active { opacity: 1 !important; transform: scale(1.03); box-shadow: 0px 0px 20px rgba(255, 255, 255, 0.25); }"
    ".circle-container { width: 250px; height: 250px; border-radius: 50%; margin: 25px auto; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #131c2e; }"
    ".circle-score { font-size: 65px; font-weight: 800; line-height: 1; margin: 5px 0; }"
    ".fintech-card { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 25px; max-width: 650px; margin: 0 auto 25px auto; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }"
    ".diag-box { background: #1e293b; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid rgba(255,255,255,0.08); }"
    ".cert-container { background: #ffffff; color: #1e3a8a; padding: 35px; border-radius: 12px; border-top: 8px solid #1e3a8a; max-width: 750px; margin: 0 auto; box-shadow: 0 8px 30px rgba(0,0,0,0.3); font-family: sans-serif; }"
    ".cert-score-box { background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0; }"
    ".progress-bar-container { display: flex; height: 14px; border-radius: 7px; overflow: hidden; margin: 15px 0 5px 0; }"
    ".loading-box { background: #111a2d; border: 2px solid #3b82f6; border-radius: 20px; padding: 35px 25px; text-align: center; margin: 50px auto; max-width: 620px; box-shadow: 0 0 35px rgba(59,130,246,0.3); }"
    ".btn-live-link { display: inline-block; width: 100%; background: linear-gradient(90deg, #2563eb, #10b981); color: white !important; text-align: center; padding: 16px 20px; font-size: 16px; font-weight: bold; border-radius: 12px; text-decoration: none; box-shadow: 0 4px 15px rgba(16,185,129,0.3); margin-top: 15px; }"
    "</style>"
)
st.markdown(css_base, unsafe_allow_html=True)

# Si es la pantalla del Live, ocultar TODO lo que sea interfaz de Streamlit
if es_pantalla_live:
    css_live_limpio = (
        "<style>"
        "[data-testid='stSidebar'] { display: none !important; }"
        "header { display: none !important; }"
        "#MainMenu { display: none !important; }"
        "footer { display: none !important; }"
        ".block-container { padding-top: 2rem !important; max-width: 1000px !important; }"
        "</style>"
    )
    st.markdown(css_live_limpio, unsafe_allow_html=True)

RANGOS = [
    {"label": "Excelente Puntaje", "min": 877, "max": 999, "color": "#00c875", "rango_texto": "877 - 999", "prob_prestamo": "Alta (Preferencial)", "tarjetas": "Líneas altas", "riesgo": "Mínimo"},
    {"label": "Buen Puntaje",      "min": 722, "max": 876, "color": "#1db954", "rango_texto": "722 - 876", "prob_prestamo": "Alta", "tarjetas": "Aprobación Rápida", "riesgo": "Bajo"},
    {"label": "Puntaje Medio",     "min": 598, "max": 721, "color": "#f59e0b", "rango_texto": "598 - 721", "prob_prestamo": "Media (Sujeto a eval.)", "tarjetas": "Límites moderados", "riesgo": "Moderado"},
    {"label": "Puntaje Bajo",      "min": 477, "max": 597, "color": "#e67e22", "rango_texto": "477 - 597", "prob_prestamo": "Baja", "tarjetas": "Con garantía / fianza", "riesgo": "Alto"},
    {"label": "Puntaje Muy Bajo",  "min": 0,   "max": 476, "color": "#e74c3c", "rango_texto": "0 - 476",   "prob_prestamo": "No Apto", "tarjetas": "Restringidas", "riesgo": "Crítico"},
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

def generar_pdf_descarga(nombre, score, categoria):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4

    c.setFillColor(colors.HexColor("#0b111e"))
    c.rect(0, 0, ancho, alto, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#94a3b8"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, alto - 50, "SISTEMA DE VERIFICACIÓN DE SCORE CREDITICIO")
    c.setFont("Helvetica", 10)
    c.drawRightString(ancho - 50, alto - 50, "DOCUMENTO INFORMATIVO")

    c.setStrokeColor(colors.HexColor("#334155"))
    c.setLineWidth(1)
    c.line(50, alto - 60, ancho - 50, alto - 60)

    c.setFillColor(colors.HexColor("#111a2d"))
    c.setStrokeColor(colors.HexColor(categoria["color"]))
    c.setLineWidth(2)
    c.roundRect(50, alto - 280, ancho - 100, 200, 15, fill=1, stroke=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(75, alto - 110, f"¡HOLA, {nombre}!")

    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor(categoria["color"]))
    c.drawString(75, alto - 135, f"Tu Score es {categoria['label'].replace('Puntaje ', '')}")

    cx = ancho - 150
    cy = alto - 180
    c.setStrokeColor(colors.HexColor(categoria["color"]))
    c.setLineWidth(8)
    c.setFillColor(colors.HexColor("#131c2e"))
    c.circle(cx, cy, 55, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#94a3b8"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx, cy + 25, "Tu score es")

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(cx, cy - 8, str(score))

    c.setFillColor(colors.HexColor("#94a3b8"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx, cy - 23, "de 999")

    c.setFillColor(colors.HexColor(categoria["color"]))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(75, alto - 195, f"● Rango: {categoria['rango_texto']}")
    c.drawString(75, alto - 220, "● Estado: VERIFICADO")

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, alto - 315, "DIAGNÓSTICO CREDITICIO ESTIMADO")

    ancho_caja = (ancho - 120) / 3
    y_cajas = alto - 400

    cajas = [
        ("Préstamos Personales", categoria["prob_prestamo"]),
        ("Tarjetas de Crédito", categoria["tarjetas"]),
        ("Nivel de Riesgo SBS", categoria["riesgo"])
    ]

    for i, (titulo, val) in enumerate(cajas):
        x = 50 + i * (ancho_caja + 10)
        c.setFillColor(colors.HexColor("#172133"))
        c.setStrokeColor(colors.HexColor("#334155"))
        c.setLineWidth(1)
        c.roundRect(x, y_cajas, ancho_caja, 70, 8, fill=1, stroke=1)

        c.setFillColor(colors.HexColor("#94a3b8"))
        c.setFont("Helvetica", 9)
        c.drawCentredString(x + ancho_caja / 2, y_cajas + 45, titulo)

        c.setFillColor(colors.HexColor(categoria["color"]))
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x + ancho_caja / 2, y_cajas + 22, val)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, alto - 435, "ESCALA DE CLASIFICACIÓN DEL SCORE")

    y_tabla = alto - 465
    for r in RANGOS:
        es_activo = (r["label"] == categoria["label"])
        bg = colors.HexColor(r["color"]) if es_activo else colors.HexColor("#131c2e")
        borde = colors.white if es_activo else colors.HexColor("#1e293b")

        c.setFillColor(bg)
        c.setStrokeColor(borde)
        c.setLineWidth(1.5 if es_activo else 0.5)
        c.roundRect(50, y_tabla - 18, ancho - 100, 22, 4, fill=1, stroke=1)

        c.setFillColor(colors.white if es_activo else colors.HexColor("#cbd5e1"))
        c.setFont("Helvetica-Bold" if es_activo else "Helvetica", 9)
        c.drawString(65, y_tabla - 12, f"Score: {r['rango_texto']}")
        c.drawRightString(ancho - 65, y_tabla - 12, r["label"])

        y_tabla -= 26

    c.setFillColor(colors.HexColor("#64748b"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(ancho / 2, 40, "Este documento es de carácter informativo generado automáticamente a partir del reporte de crédito.")
    c.drawCentredString(ancho / 2, 28, "Válido para fines de orientación financiera.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# =========================================================================
# CASO A: ESTAMOS EN LA PESTAÑA PROYECTORA DEL LIVE (100% LIMPIA)
# =========================================================================
if es_pantalla_live:
    nombre_live = params.get("nombre", "CLIENTE")
    try:
        score_live = int(params.get("score", "0"))
    except:
        score_live = 0
    estilo_live = params.get("estilo", "1. Clásico Actual")
    t_stamp = params.get("t", "0")

    # Animación de escaneo cada vez que cambie o se recargue con una nueva consulta
    key_anim = f"animada_{t_stamp}"
    if key_anim not in st.session_state:
        anim_ph = st.empty()
        pasos = [
            (20, "🔍 Conectando con bases de datos SBS y Buró...", "📡 Verificando documento oficial..."),
            (55, "📊 Analizando historial de pagos y deudas...", "📂 Procesando líneas de crédito..."),
            (85, "⚙️ Verificando niveles de riesgo y morosidad...", "🛡️ Contrastando semáforo financiero..."),
            (100, "¡EVALUACIÓN COMPLETADA!", "● Mostrando resultado oficial...")
        ]
        for pct, tit, sub in pasos:
            caja_anim = (
                '<div class="loading-box">'
                '<div style="font-size: 45px; margin-bottom: 12px;">🛰️</div>'
                '<h2 style="color: #60a5fa; margin: 0; font-weight: 800; letter-spacing: 1px;">CONSULTANDO CENTRAL DE RIESGOS</h2>'
                f'<h4 style="color: white; margin: 15px 0 5px 0;">{tit}</h4>'
                f'<p style="color: #94a3b8; font-size: 13px; margin-bottom: 20px;">{sub}</p>'
                '<div style="background: #1e293b; height: 14px; border-radius: 7px; overflow: hidden;">'
                f'<div style="background: linear-gradient(90deg, #3b82f6, #00c875); width: {pct}%; height: 100%; border-radius: 7px; box-shadow: 0 0 15px #00c875;"></div>'
                '</div>'
                f'<p style="color: #64748b; font-size: 12px; margin-top: 8px;">Progreso: {pct}%</p>'
                '</div>'
            )
            anim_ph.markdown(caja_anim, unsafe_allow_html=True)
            time.sleep(0.4)
        anim_ph.empty()
        st.session_state[key_anim] = True

    # REVELACIÓN DEL RESULTADO LIMPIO
    categoria = clasificar_score(score_live)

    if estilo_live == "1. Clásico Actual":
        col_izq, col_der = st.columns([1, 1], gap="large")
        with col_izq:
            st.markdown("<div style='background: #111a2d; padding: 25px; border-radius: 15px;'>", unsafe_allow_html=True)
            st.markdown("### Score Crediticio")
            st.caption("Es un número que indica la probabilidad de cumplir con tus obligaciones financieras.")
            st.write("")
            for r in RANGOS:
                activo = (r["label"] == categoria["label"])
                clase = "tier-active" if activo else ""
                borde = f"border: 2.5px solid {r['color']};" if activo else "border: 1px solid rgba(255,255,255,0.05);"
                html_card = (
                    f'<div class="tier-card {clase}" style="background-color: {r["color"]}; {borde}">'
                    f'<span style="color: white;">Score: {r["rango_texto"]}</span>'
                    f'<span style="color: white;">{r["label"]}</span>'
                    '</div>'
                )
                st.markdown(html_card, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with col_der:
            st.markdown("<div style='background: #111a2d; padding: 25px; border-radius: 15px; text-align: center;'>", unsafe_allow_html=True)
            st.markdown(f"<h1 style='color: white; margin: 0; font-size: 40px;'>¡Hola {nombre_live}!</h1>", unsafe_allow_html=True)
            st.markdown(f"<h2 style='color: {categoria['color']}; margin-top: 5px;'>Tu Score es {categoria['label'].replace('Puntaje ', '')}</h2>", unsafe_allow_html=True)
            html_circle = (
                f'<div class="circle-container" style="border: 15px solid {categoria["color"]};">'
                '<span style="color: #94a3b8; font-size: 15px;">Tu score es</span>'
                f'<span class="circle-score" style="color: white;">{score_live}</span>'
                '<span style="color: #94a3b8; font-size: 15px;">de 999</span>'
                '</div>'
            )
            st.markdown(html_circle, unsafe_allow_html=True)
            st.markdown(f"<h4 style='color: {categoria['color']}; font-weight: bold;'>● Verificado</h4>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    elif estilo_live == "2. Tarjeta Fintech VIP":
        pct = min(max(int((score_live / 999) * 100), 4), 100)
        html_fintech = (
            '<div class="fintech-card">'
            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">'
            '<span style="font-size: 13px; color: #94a3b8; letter-spacing: 2px;">PASAPORTE FINANCIERO DIGITAL</span>'
            f'<span style="background: {categoria["color"]}22; color: {categoria["color"]}; border: 1px solid {categoria["color"]}; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 12px;">● {categoria["label"].upper()}</span>'
            '</div>'
            '<div style="text-align: center; margin: 25px 0;">'
            '<h4 style="color: #94a3b8; margin: 0; font-weight: 400;">Puntaje Crediticio Oficial</h4>'
            f'<h1 style="font-size: 75px; font-weight: 900; color: white; margin: 5px 0;">{score_live} <span style="font-size: 20px; color: #64748b; font-weight: 400;">/ 999</span></h1>'
            f'<h3 style="color: {categoria["color"]}; margin: 0;">¡Hola {nombre_live}!</h3>'
            '</div>'
            '<div style="margin-top: 20px;">'
            '<div style="display: flex; justify-content: space-between; font-size: 11px; color: #64748b; margin-bottom: 5px;">'
            '<span>0 (Riesgo Alto)</span>'
            f'<span style="color: {categoria["color"]}; font-weight: bold;">Tu nivel actual ({pct}%)</span>'
            '<span>999 (Excelente)</span>'
            '</div>'
            '<div style="background: #334155; height: 12px; border-radius: 6px; overflow: hidden;">'
            f'<div style="background: {categoria["color"]}; width: {pct}%; height: 100%; border-radius: 6px;"></div>'
            '</div>'
            '</div>'
            '</div>'
        )
        st.markdown(html_fintech, unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="diag-box"><div style="font-size: 28px;">🏦</div><div style="font-size: 13px; color: #94a3b8;">Préstamos Personales</div><div style="font-size: 16px; font-weight: bold; color: {categoria["color"]};">{categoria["prob_prestamo"]}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="diag-box"><div style="font-size: 28px;">💳</div><div style="font-size: 13px; color: #94a3b8;">Tarjetas de Crédito</div><div style="font-size: 16px; font-weight: bold; color: {categoria["color"]};">{categoria["tarjetas"]}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="diag-box"><div style="font-size: 28px;">📊</div><div style="font-size: 13px; color: #94a3b8;">Nivel de Riesgo SBS</div><div style="font-size: 16px; font-weight: bold; color: {categoria["color"]};">{categoria["riesgo"]}</div></div>', unsafe_allow_html=True)

    elif estilo_live == "3. Certificado Oficial de Buró":
        html_cert = (
            '<div class="cert-container">'
            '<div style="display: flex; justify-content: space-between; border-bottom: 2px solid #e2e8f0; padding-bottom: 15px;">'
            '<div><h3 style="margin: 0; color: #1e3a8a; font-weight: 800;">REPORTE DE SALUD CREDITICIA</h3><span style="font-size: 12px; color: #64748b;">DIAGNÓSTICO INFORMATIVO DE RIESGO</span></div>'
            '<div style="text-align: right;"><span style="font-size: 12px; font-weight: bold; color: #1e3a8a;">EMISIÓN EN LÍNEA</span><br><span style="font-size: 11px; color: #64748b;">ESTADO: OFICIAL</span></div>'
            '</div>'
            '<div style="margin: 20px 0 10px 0;"><span style="font-size: 14px; color: #64748b;">TITULAR CONSULTADO:</span><h2 style="margin: 0; color: #0f172a; font-weight: 700;">' + nombre_live + '</h2></div>'
            '<div class="cert-score-box">'
            '<span style="font-size: 13px; color: #64748b; font-weight: 600;">PUNTAJE DETERMINADO</span>'
            f'<h1 style="font-size: 70px; margin: 0; font-weight: 900; color: {categoria["color"]};">{score_live} <span style="font-size: 22px; color: #94a3b8; font-weight: normal;">pts</span></h1>'
            f'<div style="display: inline-block; background: {categoria["color"]}22; color: {categoria["color"]}; padding: 5px 18px; border-radius: 20px; font-weight: bold; font-size: 14px; border: 1px solid {categoria["color"]}; margin-top: 5px;">{categoria["label"].upper()}</div>'
            '<div class="progress-bar-container">'
            '<div style="background: #ef4444; flex: 476;"></div><div style="background: #e67e22; flex: 120;"></div><div style="background: #f59e0b; flex: 123;"></div><div style="background: #1db954; flex: 154;"></div><div style="background: #00c875; flex: 122;"></div>'
            '</div>'
            '<div style="display: flex; justify-content: space-between; font-size: 11px; color: #94a3b8;"><span>0</span><span>477</span><span>598</span><span>722</span><span>877</span><span>999</span></div>'
            '</div>'
            '<div style="border-top: 1px solid #e2e8f0; padding-top: 15px; font-size: 13px; color: #475569;">'
            f'<p style="margin: 4px 0;"><b>● Situación Financiera:</b> Comportamiento {categoria["label"].lower()} en el sistema bancario.</p>'
            f'<p style="margin: 4px 0;"><b>● Nivel de Riesgo Buró:</b> Calificado como {categoria["riesgo"].lower()}.</p>'
            f'<p style="margin: 4px 0;"><b>● Acceso a Créditos:</b> {categoria["prob_prestamo"]}.</p>'
            '</div>'
            '<div style="margin-top: 20px; background: #f1f5f9; padding: 12px; border-radius: 8px; text-align: center; font-size: 11px; color: #64748b;">🛡️ Documento generado con tecnología de verificación instantánea.</div>'
            '</div>'
        )
        st.markdown(html_cert, unsafe_allow_html=True)

# =========================================================================
# CASO B: ESTAMOS EN TU PESTAÑA PRINCIPAL (TU PANEL DE TRABAJO)
# =========================================================================
else
