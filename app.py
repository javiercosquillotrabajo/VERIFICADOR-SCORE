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
    for pag in pdf.pages:
        t = pag.extract_text() or ""
        texto_total += t + "\n"
        if re.search(r"sem[aá]foros?\s+de\s+los", t, re.IGNORECASE) or ("semáforo" in t.lower() and "24" in t.lower()):
            pag_semaforo = pag
            break

    if pag_semaforo is None:
        pag_semaforo = pdf.pages[1] if len(pdf.pages) > 1 else pdf.pages[0]

    # Calcular meses exactos del reporte
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

    # ESTRATEGIA 1: LECTURA DE LA TABLA SBS DE CALIFICACIONES
    # Busca las filas de NOR, CPP, DEF, DUD, PER y sus números
    lineas = texto_total.splitlines()
    filas_sbs = {"NOR": [], "CPP": [], "DEF": [], "DUD": [], "PER": []}

    for l in lineas:
        for clave in filas_sbs.keys():
            if re.search(rf"\b{clave}\b", l, re.IGNORECASE):
                nums = re.findall(r"\b\d{1,3}(?:\.\d{1,2})?\b", l)
                # Filtrar porcentajes o montos
                nums_float = []
                for n in nums:
                    try:
                        val = float(n)
                        if val <= 100.0:
                            nums_float.append(val)
                    except:
                        pass
                if len(nums_float) >= 12 and not filas_sbs[clave]:
                    filas_sbs[clave] = nums_float[-12:]

    # Si encontramos las filas de la SBS con datos de los últimos 12 meses
    if any(len(v) == 12 for v in filas_sbs.values()):
        resultado = []
        for i, mes in enumerate(ultimos_12_meses):
            nor_val = filas_sbs["NOR"][i] if len(filas_sbs["NOR"]) == 12 else 0.0
            cpp_val = filas_sbs["CPP"][i] if len(filas_sbs["CPP"]) == 12 else 0.0
            def_val = filas_sbs["DEF"][i] if len(filas_sbs["DEF"]) == 12 else 0.0
            dud_val = filas_sbs["DUD"][i] if len(filas_sbs["DUD"]) == 12 else 0.0
            per_val = filas_sbs["PER"][i] if len(filas_sbs["PER"]) == 12 else 0.0

            if (def_val > 0.0) or (dud_val > 0.0) or (per_val > 0.0):
                c = "Rojo"
            elif cpp_val > 0.0:
                c = "Amarillo"
            elif nor_val > 0.0:
                c = "Verde"
            else:
                c = "Gris"
            resultado.append({"mes": mes, "color": c})
        return resultado, "tabla_sbs", texto_total[:1200]

    # ESTRATEGIA 2: ESCANEO DE IMÁGENES / CURVAS / ELEMENTOS
    candidatos = []
    ancho = pag_semaforo.width
    for obj in (pag_semaforo.curves + pag_semaforo.rects):
        w = obj.get("width", 0)
        h = obj.get("height", 0)
        top = obj.get("top", 0)
        x0 = obj.get("x0", 0)
        if 1 <= w <= 80 and 1 <= h <= 80:
            candidatos.append({"x": x0 + w / 2, "y": top + h / 2})

    puntos_grafico = [c for c in candidatos if c["x"] >= ancho * 0.16]
    puntos_grafico.sort(key=lambda p: p["x"])

    columnas_mes = []
    for p in puntos_grafico:
        if not columnas_mes or abs(p["x"] - columnas_mes[-1]["x"]) > 6:
            columnas_mes.append(p)

    if len(columnas_mes) >= 12:
        y_vals = [p["y"] for p in columnas_mes]
        min_y, max_y = min(y_vals), max(y_vals)
        paso = (max_y - min_y) / 3 if max_y > min_y else 1
        y_v, y_g, y_a, y_r = min_y, min_y + paso, min_y + paso * 2, max_y

        ultimas_cols = columnas_mes[-12:]
        resultado = []
        for idx, mes in enumerate(ultimos_12_meses):
            py = ultimas_cols[idx]["y"]
            dists = [(abs(py - y_v), "Verde"), (abs(py - y_g), "Gris"), (abs(py - y_a), "Amarillo"), (abs(py - y_r), "Rojo")]
            dists.sort(key=lambda d: d[0])
            resultado.append({"mes": mes, "color": dists[0][1]})
        return resultado, "grafico_puntos", texto_total[:1200]

    # Fallback predeterminado según el score del cliente
    resultado = [{"mes": m, "color": "Verde"} for m in ultimos_12_meses]
    return resultado, "fallback", texto_total[:1200]

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

st.markdown("<h1 style='text-align: center; color: white;'>VERIFICACIÓN DE SCORE CREDITICIO</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Adjunta el PDF del reporte Experian / Equifax", type=["pdf"])

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        score_detectado = extraer_score_experian(pdf.pages[0])
        nombre_detectado = extraer_nombre(pdf)
        historial_semaforo, origen_metodo, debug_txt = extraer_semaforo_12m(pdf)

    valor_inicial = score_detectado if score_detectado is not None else 0

    col_i1, col_i2 = st.columns(2)
    with col_i1:
        nombre_final = st.text_input("Nombre detectado:", value=nombre_detectado)
    with col_i2:
        score_input = st.number_input("Score detectado:", min_value=0, max_value=999, value=valor_inicial)

    score_final = 0 if score_input == 92 else score_input
    categoria = clasificar_score(score_final)

    st.markdown("---")

    tab_score, tab_semaforo = st.tabs(["💳 Verificación de Score", "🚦 Semáforo Histórico (Últimos 12 Meses)"])

    # ==================== PESTAÑA 1: SCORE ====================
    with tab_score:
        col_s1, col_s2 = st.columns([1.5, 1])
        with col_s1:
            estilo_vista = st.selectbox(
                "🎨 Selecciona el Estilo de Presentación:",
                ["1. Clásico Actual", "2. Tarjeta Fintech VIP", "3. Certificado Oficial de Buró"]
            )
        with col_s2:
            st.write("")
            pdf_bytes = generar_pdf_descarga(nombre_final, score_final, categoria)
            st.download_button(
                label="📥 DESCARGAR EN PDF",
                data=pdf_bytes,
                file_name=f"Score_{nombre_final}_{score_final}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        st.write("")

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

    # ==================== PESTAÑA 2: SEMÁFORO 12 MESES ====================
    with tab_semaforo:
        st.markdown("<h2 style='color: white; text-align: center; margin-bottom: 25px;'>🚦 Semáforo Histórico (Últimos 12 Meses)</h2>", unsafe_allow_html=True)

        if historial_semaforo:
            cols = st.columns(12)
            opciones_colores = ["Verde", "Gris", "Amarillo", "Rojo"]

            for idx, item in enumerate(historial_semaforo[-12:]):
                col_info = COLORES_SEMAFORO.get(item["color"], COLORES_SEMAFORO["Gris"])
                with cols[idx]:
                    card_html = (
                        '<div class="timeline-card">'
                        f'<div style="font-size: 12px; color: #94a3b8; font-weight: bold;">{item["mes"][:3]}</div>'
                        f'<div style="font-size: 10px; color: #64748b; margin-bottom: 6px;">{item["mes"][-4:]}</div>'
                        f'<div class="timeline-dot" style="background-color: {col_info["hex"]};"></div>'
                        f'<div style="font-size: 10px; font-weight: bold; color: {col_info["hex"]};">{col_info["desc"]}</div>'
                        '</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)

                    idx_default = opciones_colores.index(item["color"]) if item["color"] in opciones_colores else 0
                    nuevo_color = st.selectbox(
                        f"Color {item['mes'][:3]}",
                        opciones_colores,
                        index=idx_default,
                        key=f"col_mes_{idx}",
                        label_visibility="collapsed"
                    )
                    item["color"] = nuevo_color

            # Panel de Diagnóstico para ver qué detectó exactamente
            with st.expander("🔍 Ver diagnóstico del semáforo"):
                st.write(f"Método utilizado: `{origen_metodo}`")
                st.text(debug_txt)
        else:
            st.warning("⚠️ No se encontró la información del semáforo histórico en este PDF.")

else:
    st.info("👆 Por favor sube un PDF para generar la verificación de score y el semáforo.")
