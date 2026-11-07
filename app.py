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
    {"label": "Excelente Puntaje", "min": 877, "max": 999, "color": "#00c853", "rango_texto": "877 - 999"},
    {"label": "Buen Puntaje",      "min": 722, "max": 876, "color": "#00e676", "rango_texto": "722 - 876"},
    {"label": "Puntaje Medio",     "min": 598, "max": 721, "color": "#ffb300", "rango_texto": "598 - 721"},
    {"label": "Puntaje Bajo",      "min": 477, "max": 597, "color": "#ff6d00", "rango_texto": "477 - 597"},
    {"label": "Puntaje Muy Bajo",  "min": 0,   "max": 476, "color": "#ff1744", "rango_texto": "0 - 476"},
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
    deudas = []
    
    # 1. Determinar páginas candidatas (prioridad página 3 = índice 2)
    paginas_a_revisar = []
    if len(pdf.pages) >= 3:
        paginas_a_revisar.append(pdf.pages[2])
    for idx_p, p in enumerate(pdf.pages):
        if p not in paginas_a_revisar:
            paginas_a_revisar.append(p)

    for pag in paginas_a_revisar:
        palabras = pag.extract_words()
        if not palabras:
            continue

        # Reconstruir las filas visuales por su coordenada vertical Y
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

        # Buscar dentro de las líneas visuales de esta página
        en_tabla = False
        for l in lineas_visuales:
            l_strip = l.strip()

            if "Detalle de la deuda SBS" in l_strip or "SBS/Microfinanzas" in l_strip:
                en_tabla = True
                continue

            if en_tabla:
                # Fin de la tabla del recuadro rojo
                if "TOTAL" in l_strip.upper() or "Detalle de vencidos" in l_strip or "Utilización de Líneas" in l_strip:
                    en_tabla = False
                    break

                # Buscar la calificación SBS seguida inmediatamente por el monto
                # Ej: "... NOR 4,179.29" o "... NOR 4,179.29 15"
                m_match = re.search(r"\b(NOR|CPP|DEF|DUD|PER|SCAL)\b\s+([\d,]+\.\d{2})(?:\s+(\d{1,4}))?", l_strip)
                if m_match:
                    calif = m_match.group(1).upper()
                    monto = m_match.group(2)
                    dias = m_match.group(3) if m_match.group(3) else "0"

                    parte_antes = l_strip[:m_match.start()].strip()
                    # El nombre del banco es lo que está antes del primer número decimal o fecha
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
        if es_activo:
            c.setFillColor(colors.HexColor(r["color"]))
            c.setStrokeColor(colors.HexColor(r["color"]))
        else:
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.HexColor("#cbd5e1"))

        c.setLineWidth(2)
        c.roundRect(50, y_tabla - 18, ancho - 100, 24, 6, fill=1, stroke=1)

        if es_activo:
            c.setFillColor(colors.white)
        else:
            c.setFillColor(colors.HexColor("#0f172a"))

        c.setFont("Helvetica-Bold", 10)
        c.drawString(65, y_tabla - 12, f"Score: {r['rango_texto']}")
        c.drawRightString(ancho - 65, y_tabla - 12, r["label"])

        y_tabla -= 28

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# =========================================================================
# VISTA PÚBLICA: PESTAÑA PROYECTORA DEL LIVE (VENTANA ÚNICA)
# =========================================================================
if es_pantalla_live:
    css_limpio = (
        "<style>"
        "[data-testid='stSidebar'] { display: none !important; }"
        "header { display: none !important; }"
        "#MainMenu { display: none !important; }"
        "footer { display: none !important; }"
        ".block-container { padding-top: 1rem !important; max-width: 1050px !important; }"
        "</style>"
    )
    st.markdown(css_limpio, unsafe_allow_html=True)

    nombre_live = params.get("nombre", "CLIENTE")
    try:
        score_live = int(params.get("score", "0"))
    except:
        score_live = 0
    t_stamp = params.get("t", "0")
    bancos_raw = params.get("bancos", "")

    key_anim = f"animada_{t_stamp}"
    if key_anim not in st.session_state:
        anim_ph = st.empty()
        pasos = [
            (25, "🔍 Conectando con bases de datos SBS y Buró...", "📡 Verificando documento oficial..."),
            (60, "📊 Analizando historial financiero y créditos...", "📂 Procesando líneas bancarias..."),
            (90, "⚙️ Verificando niveles de riesgo y morosidad...", "🛡️ Contrastando semáforo del sistema..."),
            (100, "¡EVALUACIÓN COMPLETADA!", "● Mostrando resultado oficial en vivo...")
        ]
        for pct, tit, sub in pasos:
            caja_anim = (
                '<div class="loading-box">'
                '<div style="font-size: 55px; margin-bottom: 12px;">🛰️</div>'
                '<h1 style="color: #2563eb; margin: 0; font-size: 32px; font-weight: 900;">CONSULTANDO CENTRAL DE RIESGOS</h1>'
                f'<h3 style="color: #0f172a; margin: 15px 0 5px 0; font-size: 22px; font-weight: 800;">{tit}</h3>'
                f'<p style="color: #64748b; font-size: 15px; margin-bottom: 22px;">{sub}</p>'
                '<div style="background: #e2e8f0; height: 16px; border-radius: 8px; overflow: hidden;">'
                f'<div style="background: linear-gradient(90deg, #2563eb, #00c853); width: {pct}%; height: 100%; border-radius: 8px;"></div>'
                '</div>'
                f'<p style="color: #64748b; font-size: 14px; font-weight: bold; margin-top: 10px;">Progreso: {pct}%</p>'
                '</div>'
            )
            anim_ph.markdown(caja_anim, unsafe_allow_html=True)
            time.sleep(0.35)
        anim_ph.empty()
        st.session_state[key_anim] = True

    categoria = clasificar_score(score_live)

    col_nav1, col_nav2, col_nav3 = st.columns([1, 4.2, 1])
    with col_nav2:
        estilo_seleccionado = st.radio(
            "Diseño:",
            ["1. Clásico Actual", "2. Deudas por Bancos", "3. Certificado Oficial"],
            horizontal=True,
            label_visibility="collapsed"
        )

    st.write("")

    # ------------------ ESTILO 1: CLÁSICO ACTUAL ------------------
    if estilo_seleccionado == "1. Clásico Actual":
        col_izq, col_der = st.columns([1, 1], gap="large")

        html_cards = ""
        for r in RANGOS:
            activo = (r["label"] == categoria["label"])
            clase = "tier-active" if activo else ""
            borde = f"border: 3.5px solid {r['color']};" if activo else "border: 1.5px solid #cbd5e1;"
            html_cards += (
                f'<div class="tier-card {clase}" style="background-color: {r["color"]}; {borde}">'
                f'<span>Score: {r["rango_texto"]}</span>'
                f'<span>{r["label"]}</span>'
                '</div>'
            )

        with col_izq:
            html_izq = (
                '<div class="card-panel">'
                '<h2 style="margin-top:0; font-size: 30px; font-weight: 900;">Score Crediticio</h2>'
                '<p style="font-size: 15px; color: #64748b; margin-bottom: 22px; font-weight: 600;">Probabilidad de cumplimiento en el sistema financiero.</p>'
                + html_cards +
                '</div>'
            )
            st.markdown(html_izq, unsafe_allow_html=True)

        with col_der:
            html_der = (
                '<div class="card-panel" style="text-align: center;">'
                f'<h1 style="margin: 0; font-size: 50px; font-weight: 900; color: #0f172a;">¡Hola {nombre_live}!</h1>'
                f'<h2 style="color: {categoria["color"]}; margin-top: 8px; font-size: 34px; font-weight: 900;">Tu Score es {categoria["label"].replace("Puntaje ", "")}</h2>'
                f'<div class="circle-container" style="border: 20px solid {categoria["color"]};">'
                '<span style="color: #64748b; font-size: 18px; font-weight: 800;">Tu score es</span>'
                f'<span class="circle-score" style="color: {categoria["color"]};">{score_live}</span>'
                '<span style="color: #64748b; font-size: 18px; font-weight: 800;">de 999</span>'
                '</div>'
                f'<h3 style="color: {categoria["color"]}; font-weight: 900; font-size: 26px; margin: 8px 0;">● VERIFICADO</h3>'
                '</div>'
            )
            st.markdown(html_der, unsafe_allow_html=True)

    # ------------------ ESTILO 2: DEUDAS POR BANCOS (RECUADRO ROJO) ------------------
    if estilo_seleccionado == "2. Deudas por Bancos":
        lista_deudas = []
        if bancos_raw:
            for item in urllib.parse.unquote(bancos_raw).split("~"):
                partes = item.split("*")
                if len(partes) >= 4:
                    lista_deudas.append({
                        "banco": partes[0],
                        "monto": partes[1],
                        "calif": partes[2],
                        "dias": partes[3]
                    })

        total_soles = 0.0
        for d in lista_deudas:
            try:
                total_soles += float(d["monto"].replace(",", ""))
            except:
                pass

        total_fmt = f"{total_soles:,.2f}"

        html_bancos_body = ""
        if lista_deudas:
            for d in lista_deudas:
                info_sbs = COLORES_SBS.get(d["calif"], COLORES_SBS["NOR"])
                dias_txt = "Al día (0 días)" if (d["dias"] == "0" or not d["dias"]) else f"{d['dias']} días atraso"
                html_bancos_body += (
                    '<div class="bank-card">'
                    '<div>'
                    f'<div style="font-size: 22px; font-weight: 900; color: #0f172a; margin-bottom: 5px;">🏦 {d["banco"]}</div>'
                    f'<div style="font-size: 15px; font-weight: 700; color: #64748b;">Deuda actual: <span style="font-size: 24px; font-weight: 900; color: #0f172a;">S/ {d["monto"]}</span></div>'
                    '</div>'
                    f'<div class="bank-badge" style="background-color: {info_sbs["color"]};">'
                    f'{info_sbs["nombre"]} • {dias_txt}'
                    '</div>'
                    '</div>'
                )
        else:
            html_bancos_body = (
                '<div style="background: white; border: 2.5px dashed #94a3b8; border-radius: 20px; padding: 45px; text-align: center;">'
                '<div style="font-size: 45px; margin-bottom: 10px;">✅</div>'
                '<h2 style="margin: 0; color: #00c853; font-weight: 900;">NO REGISTRA DEUDAS SBS</h2>'
                '<p style="color: #64748b; margin-top: 8px; font-weight: bold; font-size: 16px;">Deuda actual: S/ 0.00 en el sistema financiero.</p>'
                '</div>'
            )

        html_bancos_completo = (
            '<div style="max-width: 900px; margin: 0 auto;">'
            '<div class="total-deuda-banner">'
            '<div>'
            '<div style="font-size: 14px; color: #94a3b8; font-weight: 800; letter-spacing: 1px;">DETALLE DE DEUDA SBS / MICROFINANZAS</div>'
            f'<div style="font-size: 30px; font-weight: 900; margin-top: 4px; color: white;">{nombre_live}</div>'
            '</div>'
            '<div style="text-align: right;">'
            '<div style="font-size: 13px; color: #94a3b8; font-weight: 800;">DEUDA TOTAL REGISTRADA</div>'
            f'<div style="font-size: 38px; font-weight: 900; color: #38bdf8;">S/ {total_fmt}</div>'
            '</div>'
            '</div>'
            + html_bancos_body +
            '</div>'
        )
        st.markdown(html_bancos_completo, unsafe_allow_html=True)

    # ------------------ ESTILO 3: CERTIFICADO OFICIAL ------------------
    if estilo_seleccionado == "3. Certificado Oficial":
        html_cert = (
            '<div class="cert-container">'
            '<div style="display: flex; justify-content: space-between; border-bottom: 3px solid #cbd5e1; padding-bottom: 18px;">'
            '<div><h2 style="margin: 0; color: #1e3a8a; font-size: 28px; font-weight: 900;">REPORTE DE SALUD CREDITICIA</h2><span style="font-size: 15px; color: #64748b; font-weight: 800;">DIAGNÓSTICO INFORMATIVO DE RIESGO</span></div>'
            '<div style="text-align: right;"><span style="font-size: 15px; font-weight: 900; color: #1e3a8a;">EMISIÓN EN VIVO</span><br><span style="font-size: 14px; color: #00c853; font-weight: 900;">● OFICIAL</span></div>'
            '</div>'
            '<div style="margin: 22px 0 10px 0;"><span style="font-size: 15px; color: #64748b; font-weight: 800;">TITULAR CONSULTADO:</span><h1 style="margin: 0; color: #0f172a; font-size: 46px; font-weight: 900;">' + nombre_live + '</h1></div>'
            '<div class="cert-score-box">'
            '<span style="font-size: 16px; color: #64748b; font-weight: 900; letter-spacing: 1px;">PUNTAJE DETERMINADO</span>'
            f'<h1 style="font-size: 88px; margin: 4px 0; font-weight: 900; color: {categoria["color"]};">{score_live} <span style="font-size: 28px; color: #64748b; font-weight: normal;">pts</span></h1>'
            f'<div style="display: inline-block; background: {categoria["color"]}22; color: {categoria["color"]}; padding: 6px 24px; border-radius: 20px; font-weight: 900; font-size: 17px; border: 2.5px solid {categoria["color"]}; margin-top: 5px;">{categoria["label"].upper()}</div>'
            '<div class="progress-bar-container">'
            '<div style="background: #ff1744; flex: 476;"></div><div style="background: #ff6d00; flex: 120;"></div><div style="background: #ffb300; flex: 123;"></div><div style="background: #00e676; flex: 154;"></div><div style="background: #00c853; flex: 122;"></div>'
            '</div>'
            '<div style="display: flex; justify-content: space-between; font-size: 13px; color: #475569; font-weight: 900;"><span>0</span><span>477</span><span>598</span><span>722</span><span>877</span><span>999</span></div>'
            '</div>'
            '<div style="border-top: 2.5px solid #cbd5e1; padding-top: 18px; font-size: 16px; color: #1e293b; line-height: 1.6;">'
            f'<p style="margin: 6px 0;"><b>● Situación Financiera:</b> Comportamiento {categoria["label"].lower()} para operaciones en el sistema bancario.</p>'
            f'<p style="margin: 4px 0;"><b>● Nivel de Riesgo Buró:</b> Calificado como {categoria["riesgo"].lower()}.</p>'
            f'<p style="margin: 4px 0;"><b>● Capacidad de Acceso:</b> {categoria["prob_prestamo"]}.</p>'
            '</div>'
            '<div style="margin-top: 20px; background: #f8fafc; border: 2px solid #cbd5e1; padding: 14px; border-radius: 12px; text-align: center; font-size: 14px; font-weight: 800; color: #334155;">🛡️ Verificado con tecnología de consulta instantánea SBS y Buró.</div>'
            '</div>'
        )
        st.markdown(html_cert, unsafe_allow_html=True)

    st.stop()


# =========================================================================
# VISTA PRIVADA: TU PANEL DE CONTROL (CONTROL DE LA VENTANA ÚNICA)
# =========================================================================
st.markdown("<h1 style='text-align: center; font-size: 38px; font-weight: 900;'>🎛️ PANEL DE CONTROL (PRIVADO)</h1>", unsafe_allow_html=True)
st.caption("Esta pestaña es tu consola privada. Al pulsar el botón, actualizará la MISMA ventana del Live sin abrir pestañas nuevas.")

uploaded_file = st.file_uploader("📂 Sube aquí el PDF del reporte", type=["pdf"])

detected_nombre = "CLIENTE"
detected_score = 0
detected_deudas = []

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        s = extraer_score_experian(pdf.pages[0])
        n = extraer_nombre(pdf)
        d_sbs = extraer_deudas_sbs(pdf)
        if s is not None:
            detected_score = s
        if n:
            detected_nombre = n
        if d_sbs:
            detected_deudas = d_sbs

col_c1, col_c2 = st.columns(2)
with col_c1:
    nombre_final = st.text_input("Nombre detectado (editable):", value=detected_nombre)
with col_c2:
    score_input = st.number_input("Score detectado (editable):", min_value=0, max_value=999, value=detected_score)

score_val = 0 if score_input == 92 else score_input

# Confirmación visible en tu panel de control de los bancos encontrados
if detected_deudas:
    nombres_bancos = ", ".join([f"{d['banco']} (S/ {d['monto']})" for d in detected_deudas])
    st.success(f"✅ Se detectaron {len(detected_deudas)} bancos con deuda en la Página 3: {nombres_bancos}")
else:
    st.info("ℹ️ No se detectaron deudas en este reporte o el cliente tiene S/ 0.00.")

cadena_deudas = "~".join([f"{d['banco']}*{d['monto']}*{d['calif']}*{d['dias']}" for d in detected_deudas])
bancos_enc = urllib.parse.quote(cadena_deudas)

nombre_encoded = urllib.parse.quote(nombre_final)
t_now = int(time.time())
url_live_completa = f"https://score-verificador.streamlit.app/?live=1&nombre={nombre_encoded}&score={score_val}&bancos={bancos_enc}&t={t_now}"

btn_code = (
    '<!DOCTYPE html><html><head><style>'
    'body { margin: 0; padding: 0; background: transparent; font-family: "Segoe UI", Tahoma, sans-serif; }'
    '.btn-live {'
    '  display: block; width: 100%; border: none; outline: none; cursor: pointer;'
    '  background: linear-gradient(90deg, #2563eb, #00c853);'
    '  color: #ffffff; text-align: center;'
    '  padding: 16px 20px; font-size: 18px; font-weight: 900;'
    '  border-radius: 14px; text-decoration: none;'
    '  box-shadow: 0 6px 20px rgba(37,99,235,0.3);'
    '  transition: transform 0.1s, opacity 0.1s;'
    '}'
    '.btn-live:hover { opacity: 0.95; }'
    '.btn-live:active { transform: scale(0.99); }'
    '</style></head><body>'
    f'<button type="button" class="btn-live" onclick="window.open(\'{url_live_completa}\', \'pantalla_live_unica\');">'
    '🚀 ACTUALIZAR VENTANA ÚNICA DEL LIVE'
    '</button>'
    '</body></html>'
)
components.html(btn_code, height=75)

st.markdown("---")
cat_priv = clasificar_score(score_val)
pdf_bytes = generar_pdf_descarga(nombre_final, score_val, cat_priv)
st.download_button(
    label="📥 Guardar PDF descargable",
    data=pdf_bytes,
    file_name=f"Score_{nombre_final}_{score_val}.pdf",
    mime="application/pdf"
)
