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
    """Genera un archivo PDF elegante con el resultado crediticio."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4

    # Fondo oscuro profesional
    c.setFillColor(colors.HexColor("#0b111e"))
    c.rect(0, 0, ancho, alto, fill=1, stroke=0)

    # Cabecera
    c.setFillColor(colors.HexColor("#94a3b8"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, alto - 50, "SISTEMA DE VERIFICACIÓN DE SCORE CREDITICIO")
    c.setFont("Helvetica", 10)
    c.drawRightString(ancho - 50, alto - 50, "DOCUMENTO INFORMATIVO")

    c.setStrokeColor(colors.HexColor("#334155"))
    c.setLineWidth(1)
    c.line(50, alto - 60, ancho - 50, alto - 60)

    # Recuadro Principal
    c.setFillColor(colors.HexColor("#111a2d"))
    c.setStrokeColor(colors.HexColor(categoria["color"]))
    c.setLineWidth(2)
    c.roundRect(50, alto - 280, ancho - 100, 200, 15, fill=1, stroke=1)

    # Saludo y Nombre
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(75, alto - 110, f"¡HOLA, {nombre}!")

    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor(categoria["color"]))
    c.drawString(75, alto - 135, f"Tu Score es {categoria['label'].replace('Puntaje ', '')}")

    # Círculo del Score
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

    # Datos adicionales en el recuadro
    c.setFillColor(colors.HexColor(categoria["color"]))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(75, alto - 195, f"● Rango: {categoria['rango_texto']}")
    c.drawString(75, alto - 220, "● Estado: VERIFICADO")

    # 3 Tarjetas de Diagnóstico
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

    # Escala SBS / Buró
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

    # Pie de página
    c.setFillColor(colors.HexColor("#64748b"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(ancho / 2, 40, "Este documento es de carácter informativo generado automáticamente a partir del reporte de crédito.")
    c.drawCentredString(ancho / 2, 28, "Válido para fines de orientación financiera.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

st.markdown("<h1 style='text-align: center; color: white;'>VERIFICACIÓN DE SCORE CREDITICIO</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Adjunta el PDF del reporte Experian / Equifax", type=["pdf"])

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        score_detectado = extraer_score_experian(pdf.pages[0])
        nombre_detectado = extraer_nombre(pdf)

    valor_inicial = score_detectado if score_detectado is not None else 0

    col_i1, col_i2, col_i3 = st.columns([1, 1, 1.2])
    with col_i1:
        nombre_final = st.text_input("Nombre detectado:", value=nombre_detectado)
    with col_i2:
        score_input = st.number_input("Score detectado:", min_value=0, max_value=999, value=valor_inicial)
    with col_i3:
        estilo_vista = st.selectbox(
            "🎨 Selecciona el Estilo de Presentación:",
            ["1. Clásico Actual", "2. Tarjeta Fintech VIP", "3. Certificado Oficial de Buró"]
        )

    score_final = 0 if score_input == 92 else score_input
    categoria = clasificar_score(score_final)

    # BOTÓN DE DESCARGA PDF CENTRADO
    st.write("")
    col_b1, col_b2, col_b3 = st.columns([1, 1.5, 1])
    with col_b2:
        pdf_bytes = generar_pdf_descarga(nombre_final, score_final, categoria)
        st.download_button(
            label="📥 DESCARGAR RESULTADO EN PDF",
            data=pdf_bytes,
            file_name=f"Score_{nombre_final}_{score_final}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    st.markdown("---")

    # ==================== OPCION 1: CLASICO ACTUAL ====================
    if estilo_vista == "1. Clásico Actual":
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
            st.markdown(f"<h1 style='color: white; margin: 0;'>¡Hola {nombre_final}!</h1>", unsafe_allow_html=True)
            st.markdown(f"<h2 style='color: {categoria['color']}; margin-top: 5px;'>Tu Score es {categoria['label'].replace('Puntaje ', '')}</h2>", unsafe_allow_html=True)
            html_circle = (
                f'<div class="circle-container" style="border: 14px solid {categoria["color"]};">'
                '<span style="color: #94a3b8; font-size: 15px;">Tu score es</span>'
                f'<span class="circle-score" style="color: white;">{score_final}</span>'
                '<span style="color: #94a3b8; font-size: 15px;">de 999</span>'
                '</div>'
            )
            st.markdown(html_circle, unsafe_allow_html=True)
            st.markdown(f"<h4 style='color: {categoria['color']}; font-weight: bold;'>● Verificado</h4>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # ==================== OPCION 2: TARJETA FINTECH VIP ====================
    elif estilo_vista == "2. Tarjeta Fintech VIP":
        pct = min(max(int((score_final / 999) * 100), 4), 100)
        html_fintech = (
            '<div class="fintech-card">'
            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">'
            '<span style="font-size: 13px; color: #94a3b8; letter-spacing: 2px;">PASAPORTE FINANCIERO DIGITAL</span>'
            f'<span style="background: {categoria["color"]}22; color: {categoria["color"]}; border: 1px solid {categoria["color"]}; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 12px;">● {categoria["label"].upper()}</span>'
            '</div>'
            '<div style="text-align: center; margin: 25px 0;">'
            '<h4 style="color: #94a3b8; margin: 0; font-weight: 400;">Puntaje Crediticio Oficial</h4>'
            f'<h1 style="font-size: 75px; font-weight: 900; color: white; margin: 5px 0;">{score_final} <span style="font-size: 20px; color: #64748b; font-weight: 400;">/ 999</span></h1>'
            f'<h3 style="color: {categoria["color"]}; margin: 0;">¡Hola {nombre_final}!</h3>'
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
            h1 = (
                '<div class="diag-box">'
                '<div style="font-size: 28px; margin-bottom: 5px;">🏦</div>'
                '<div style="font-size: 13px; color: #94a3b8;">Préstamos Personales</div>'
                f'<div style="font-size: 16px; font-weight: bold; color: {categoria["color"]}; margin-top: 4px;">{categoria["prob_prestamo"]}</div>'
                '</div>'
            )
            st.markdown(h1, unsafe_allow_html=True)
        with c2:
            h2 = (
                '<div class="diag-box">'
                '<div style="font-size: 28px; margin-bottom: 5px;">💳</div>'
                '<div style="font-size: 13px; color: #94a3b8;">Tarjetas de Crédito</div>'
                f'<div style="font-size: 16px; font-weight: bold; color: {categoria["color"]}; margin-top: 4px;">{categoria["tarjetas"]}</div>'
                '</div>'
            )
            st.markdown(h2, unsafe_allow_html=True)
        with c3:
            h3 = (
                '<div class="diag-box">'
                '<div style="font-size: 28px; margin-bottom: 5px;">📊</div>'
                '<div style="font-size: 13px; color: #94a3b8;">Nivel de Riesgo SBS</div>'
                f'<div style="font-size: 16px; font-weight: bold; color: {categoria["color"]}; margin-top: 4px;">{categoria["riesgo"]}</div>'
                '</div>'
            )
            st.markdown(h3, unsafe_allow_html=True)

    # ==================== OPCION 3: CERTIFICADO OFICIAL ====================
    elif estilo_vista == "3. Certificado Oficial de Buró":
        html_cert = (
            '<div class="cert-container">'
            '<div style="display: flex; justify-content: space-between; border-bottom: 2px solid #e2e8f0; padding-bottom: 15px;">'
            '<div>'
            '<h3 style="margin: 0; color: #1e3a8a; font-weight: 800;">REPORTE DE SALUD CREDITICIA</h3>'
            '<span style="font-size: 12px; color: #64748b;">DIAGNÓSTICO INFORMATIVO DE RIESGO</span>'
            '</div>'
            '<div style="text-align: right;">'
            '<span style="font-size: 12px; font-weight: bold; color: #1e3a8a;">EMISIÓN EN LÍNEA</span><br>'
            '<span style="font-size: 11px; color: #64748b;">ESTADO: OFICIAL</span>'
            '</div>'
            '</div>'
            '<div style="margin: 20px 0 10px 0;">'
            '<span style="font-size: 14px; color: #64748b;">TITULAR CONSULTADO:</span>'
            f'<h2 style="margin: 0; color: #0f172a; font-weight: 700;">{nombre_final}</h2>'
            '</div>'
            '<div class="cert-score-box">'
            '<span style="font-size: 13px; color: #64748b; font-weight: 600; letter-spacing: 1px;">PUNTAJE DETERMINADO</span>'
            f'<h1 style="font-size: 70px; margin: 0; font-weight: 900; color: {categoria["color"]};">{score_final} <span style="font-size: 22px; color: #94a3b8; font-weight: normal;">pts</span></h1>'
            f'<div style="display: inline-block; background: {categoria["color"]}22; color: {categoria["color"]}; padding: 5px 18px; border-radius: 20px; font-weight: bold; font-size: 14px; border: 1px solid {categoria["color"]}; margin-top: 5px;">{categoria["label"].upper()}</div>'
            '<div class="progress-bar-container">'
            '<div style="background: #ef4444; flex: 476;"></div>'
            '<div style="background: #e67e22; flex: 120;"></div>'
            '<div style="background: #f59e0b; flex: 123;"></div>'
            '<div style="background: #1db954; flex: 154;"></div>'
            '<div style="background: #00c875; flex: 122;"></div>'
            '</div>'
            '<div style="display: flex; justify-content: space-between; font-size: 11px; color: #94a3b8;">'
            '<span>0</span><span>477</span><span>598</span><span>722</span><span>877</span><span>999</span>'
            '</div>'
            '</div>'
            '<div style="border-top: 1px solid #e2e8f0; padding-top: 15px; font-size: 13px; color: #475569;">'
            f'<p style="margin: 4px 0;"><b>● Situación Financiera:</b> Comportamiento {categoria["label"].lower()} en el sistema bancario.</p>'
            f'<p style="margin: 4px 0;"><b>● Nivel de Riesgo Buró:</b> Calificado como {categoria["riesgo"].lower()}.</p>'
            f'<p style="margin: 4px 0;"><b>● Acceso a Créditos:</b> {categoria["prob_prestamo"]}.</p>'
            '</div>'
            '<div style="margin-top: 20px; background: #f1f5f9; padding: 12px; border-radius: 8px; text-align: center; font-size: 11px; color: #64748b;">'
            '🛡️ Documento de consulta generado con tecnología de verificación instantánea.'
            '</div>'
            '</div>'
        )
        st.markdown(html_cert, unsafe_allow_html=True)

else:
    st.info("👆 Por favor sube un PDF para generar la ficha de score.")
