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
    ".stApp { background-color: #0a0f1d; color: #ffffff; -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }"
    "h1, h2, h3, h4, h5, p, span { font-family: 'Segoe UI', Tahoma, Arial, sans-serif; }"
    ".single-card { background: #151e32; border: 2.5px solid #334155; border-radius: 26px; padding: 32px 24px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); text-align: center; margin: 0 auto; max-width: 590px; }"
    ".circle-container { width: 250px; height: 250px; border-radius: 50%; margin: 20px auto; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #0f172a; box-shadow: 0 15px 40px rgba(0,0,0,0.4); }"
    ".circle-score { font-size: 88px; font-weight: 900; line-height: 1; margin: 2px 0; }"
    ".mini-scale-bar { display: flex; gap: 6px; justify-content: space-between; margin-top: 18px; }"
    ".mini-pill { flex: 1; padding: 12px 4px; border-radius: 12px; font-size: 13px; font-weight: 900; opacity: 0.45; text-align: center; letter-spacing: 0.5px; }"
    ".mini-pill-active { opacity: 1 !important; transform: scale(1.1); box-shadow: 0 0 25px currentColor !important; border: 2.5px solid #ffffff !important; }"
    ".stacked-tier { padding: 14px 20px; border-radius: 14px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; font-weight: 900; font-size: 18px; opacity: 0.45; transition: all 0.2s ease; }"
    ".stacked-active { opacity: 1 !important; transform: scale(1.04); box-shadow: 0 0 25px currentColor !important; border: 3px solid #ffffff !important; }"
    ".bank-card { background: #151e32; border: 2px solid #334155; border-radius: 18px; padding: 20px 24px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }"
    ".bank-badge { padding: 10px 20px; border-radius: 25px; font-weight: 900; font-size: 15px; color: #ffffff; text-align: center; letter-spacing: 0.5px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }"
    ".total-deuda-banner { background: linear-gradient(135deg, #1e40af, #0f172a); border-radius: 20px; padding: 22px 28px; color: white; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; box-shadow: 0 15px 40px rgba(30,64,175,0.4); border: 2px solid #38bdf8; }"
    ".total-vencidos-banner { background: linear-gradient(135deg, #b91c1c, #450a0a); border-radius: 20px; padding: 22px 28px; color: white; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; box-shadow: 0 15px 40px rgba(185,28,28,0.4); border: 2px solid #f87171; }"
    ".loading-box { background: #151e32; border: 3.5px solid #3b82f6; border-radius: 24px; padding: 45px 30px; text-align: center; margin: 30px auto; max-width: 590px; box-shadow: 0 0 50px rgba(59,130,246,0.3); }"
    "div[data-testid='stRadio'] > div { justify-content: center; gap: 8px; background: #151e32; padding: 8px 16px; border-radius: 35px; border: 2px solid #334155; box-shadow: 0 8px 25px rgba(0,0,0,0.4); }"
    "div[data-testid='stRadio'] label span { font-weight: 900 !important; font-size: 14px !important; color: #f8fafc !important; }"
    "</style>"
)
st.markdown(css_base, unsafe_allow_html=True)

# PALETA VIBRANTE DE ALTO CONTRASTE
RANGOS = [
    {"label": "Excelente Puntaje", "min": 877, "max": 999, "color": "#00e676", "texto_col": "#000000", "rango_texto": "877 - 999", "corto": "Excelente"},
    {"label": "Buen Puntaje",      "min": 722, "max": 876, "color": "#10b981", "texto_col": "#ffffff", "rango_texto": "722 - 876", "corto": "Bueno"},
    {"label": "Puntaje Medio",     "min": 598, "max": 721, "color": "#fbbf24", "texto_col": "#000000", "rango_texto": "598 - 721", "corto": "Medio"},
    {"label": "Puntaje Bajo",      "min": 477, "max": 597, "color": "#f97316", "texto_col": "#ffffff", "rango_texto": "477 - 597", "corto": "Bajo"},
    {"label": "Puntaje Muy Bajo",  "min": 0,   "max": 476, "color": "#ef4444", "texto_col": "#ffffff", "rango_texto": "0 - 476",   "corto": "Muy Bajo"},
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
                if "Utilización de Líneas" in l_strip or "Otros documentos" in l_strip or "Semáforos de los" in l_strip or "TOTAL" in l_strip.upper():
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

                    if acreedor_nom and len(acreedor_nom) > 2:
                        vencidos.append({
                            "acreedor": acreedor_nom,
                            "monto": monto_val,
                            "dias": dias_val
                        })

        if vencidos:
            break

    return vencidos

def generar_pdf_descarga(nombre, score, categoria):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4

    c.setFillColor(colors.HexColor("#0a0f1d"))
    c.rect(0, 0, ancho, alto, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#38bdf8"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, alto - 50, "VERIFICACIÓN DE SCORE CREDITICIO")

    c.setStrokeColor(colors.HexColor("#334155"))
    c.setLineWidth(1.5)
    c.line(50, alto - 60, ancho - 50, alto - 60)

    c.setFillColor(colors.HexColor("#151e32"))
    c.setStrokeColor(colors.HexColor(categoria["color"]))
    c.setLineWidth(2.5)
    c.roundRect(50, alto - 280, ancho - 100, 200, 15, fill=1, stroke=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(75, alto - 110, f"¡HOLA, {nombre}!")

    c.setFont("Helvetica-Bold", 15)
    c.setFillColor(colors.HexColor(categoria["color"]))
    c.drawString(75, alto - 138, f"Tu Score es {categoria['label'].replace('Puntaje ', '')}")

    cx = ancho - 150
    cy = alto - 180
    c.setStrokeColor(colors.HexColor(categoria["color"]))
    c.setLineWidth(9)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.circle(cx, cy, 58, fill=1, stroke=1)

    c.setFillColor(colors.HexColor("#94a3b8"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(cx, cy + 26, "Tu score es")

    c.setFillColor(colors.HexColor(categoria["color"]))
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(cx, cy - 10, str(score))

    c.setFillColor(colors.HexColor("#94a3b8"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(cx, cy - 26, "de 999")

    c.setFillColor(colors.HexColor(categoria["color"]))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(75, alto - 195, f"● Rango: {categoria['rango_texto']}")
    c.drawString(75, alto - 222, "● Estado: VERIFICADO")

    y_tabla = alto - 320
    for r in RANGOS:
        es_activo = (r["label"] == categoria["label"])
        bg = colors.HexColor(r["color"]) if es_activo else colors.HexColor("#1e293b")
        borde = colors.HexColor(r["color"]) if es_activo else colors.HexColor("#334155")

        c.setFillColor(bg)
        c.setStrokeColor(borde)
        c.setLineWidth(2 if es_activo else 1)
        c.roundRect(50, y_tabla - 18, ancho - 100, 24, 6, fill=1, stroke=1)

        c.setFillColor(colors.white if es_activo else colors.HexColor("#cbd5e1"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(65, y_tabla - 12, f"Score: {r['rango_texto']}")
        c.drawRightString(ancho - 65, y_tabla - 12, r["label"])

        y_tabla -= 28

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# =========================================================================
# VISTA PÚBLICA: PESTAÑA PROYECTORA DEL LIVE (AZUL NOCHE + COLORES VIBRANTES)
# =========================================================================
if es_pantalla_live:
    css_limpio = (
        "<style>"
        "[data-testid='stSidebar'] { display: none !important; }"
        "header { display: none !important; }"
        "#MainMenu { display: none !important; }"
        "footer { display: none !important; }"
        ".block-container { padding: 0.6rem 0.6rem !important; max-width: 610px !important; margin: 0 auto !important; }"
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
    vencidos_raw = params.get("vencidos", "")

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
                '<div style="font-size: 50px; margin-bottom: 8px;">🛰️</div>'
                '<h2 style="color: #38bdf8; margin: 0; font-size: 26px; font-weight: 900;">CONSULTANDO CENTRAL DE RIESGOS</h2>'
                f'<h4 style="color: #ffffff; margin: 12px 0 4px 0; font-size: 19px; font-weight: 900;">{tit}</h4>'
                f'<p style="color: #94a3b8; font-size: 14px; margin-bottom: 18px; font-weight: 700;">{sub}</p>'
                '<div style="background: #0f172a; height: 16px; border-radius: 8px; overflow: hidden; border: 1px solid #334155;">'
                f'<div style="background: linear-gradient(90deg, #38bdf8, #00e676); width: {pct}%; height: 100%; border-radius: 8px; box-shadow: 0 0 15px #00e676;"></div>'
                '</div>'
                f'<p style="color: #38bdf8; font-size: 13px; font-weight: 900; margin-top: 8px;">Progreso: {pct}%</p>'
                '</div>'
            )
            anim_ph.markdown(caja_anim, unsafe_allow_html=True)
            time.sleep(0.35)
        anim_ph.empty()
        st.session_state[key_anim] = True

    categoria = clasificar_score(score_live)

    # 4 BOTONES DE NAVEGACIÓN EN AZUL NOCHE
    estilo_seleccionado = st.radio(
        "Diseño:",
        ["1. Score Círculo", "2. Score Lista", "3. Deudas Bancarias", "4. Otras Deudas"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.write("")

    # ------------------ OPCIÓN 1: TARJETA HERO VERTICAL (CÍRCULO + PASTILLAS) ------------------
    if estilo_seleccionado == "1. Score Círculo":
        html_pills = ""
        for r in RANGOS:
            es_act = (r["label"] == categoria["label"])
            clase_p = "mini-pill mini-pill-active" if es_act else "mini-pill"
            html_pills += f'<div class="{clase_p}" style="background-color: {r["color"]}; color: {r["texto_col"]} !important;">{r["corto"]}</div>'

        card_unificada = (
            '<div class="single-card">'
            f'<h1 style="margin: 0; font-size: 52px; font-weight: 900; color: #ffffff; letter-spacing: 1px;">¡Hola {nombre_live}!</h1>'
            f'<h2 style="color: {categoria["color"]}; margin-top: 6px; font-size: 30px; font-weight: 900; text-shadow: 0 0 20px {categoria["color"]}66;">Tu Score es {categoria["label"].replace("Puntaje ", "")}</h2>'
            f'<div class="circle-container" style="border: 20px solid {categoria["color"]}; box-shadow: 0 0 40px {categoria["color"]}44;">'
            '<span style="color: #94a3b8; font-size: 18px; font-weight: 900;">Tu score es</span>'
            f'<span class="circle-score" style="color: {categoria["color"]}; text-shadow: 0 0 25px {categoria["color"]}88;">{score_live}</span>'
            '<span style="color: #94a3b8; font-size: 18px; font-weight: 900;">de 999</span>'
            '</div>'
            f'<h3 style="color: {categoria["color"]}; font-weight: 900; font-size: 24px; margin: 6px 0 18px 0; letter-spacing: 1px;">● VERIFICADO</h3>'
            '<div style="border-top: 2px solid #334155; padding-top: 16px;">'
            '<div style="font-size: 14px; font-weight: 900; color: #94a3b8; letter-spacing: 1.5px; margin-bottom: 10px;">ESCALA DE CLASIFICACIÓN SBS</div>'
            '<div class="mini-scale-bar">'
            + html_pills +
            '</div>'
            '</div>'
            '</div>'
        )
        st.markdown(card_unificada, unsafe_allow_html=True)

    # ------------------ OPCIÓN 2: LISTA EJECUTIVA APILADA (BARRAS ANCHAS) ------------------
    if estilo_seleccionado == "2. Score Lista":
        html_barras = ""
        for r in RANGOS:
            es_act = (r["label"] == categoria["label"])
            clase_b = "stacked-tier stacked-active" if es_act else "stacked-tier"
            indicador = "  ◄" if es_act else ""
            html_barras += (
                f'<div class="{clase_b}" style="background-color: {r["color"]}; color: {r["texto_col"]} !important;">'
                f'<span>Score: {r["rango_texto"]}</span>'
                f'<span>{r["label"]}{indicador}</span>'
                '</div>'
            )

        card_apilada = (
            '<div class="single-card" style="text-align: left; padding: 28px 24px;">'
            f'<div style="text-align: center; border-bottom: 2px solid #334155; padding-bottom: 16px; margin-bottom: 18px;">'
            f'<h1 style="margin: 0; font-size: 48px; font-weight: 900; color: #ffffff;">¡Hola {nombre_live}!</h1>'
            f'<h2 style="color: {categoria["color"]}; margin: 6px 0 0 0; font-size: 32px; font-weight: 900; text-shadow: 0 0 20px {categoria["color"]}66;">{score_live} pts — {categoria["label"]}</h2>'
            f'</div>'
            '<div style="font-size: 14px; font-weight: 900; color: #94a3b8; margin-bottom: 12px; text-align: center; letter-spacing: 1px;">TABLA DE EVALUACIÓN OFICIAL SBS</div>'
            + html_barras +
            f'<div style="text-align: center; margin-top: 16px; font-size: 18px; font-weight: 900; color: {categoria["color"]};">● VERIFICADO POR BURÓ PRIVADO</div>'
            '</div>'
        )
        st.markdown(card_apilada, unsafe_allow_html=True)

    # ------------------ OPCIÓN 3: DEUDAS BANCARIAS (SBS) ------------------
    if estilo_seleccionado == "3. Deudas Bancarias":
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
                    f'<div style="font-size: 22px; font-weight: 900; color: #ffffff; margin-bottom: 5px;">🏦 {d["banco"]}</div>'
                    f'<div style="font-size: 15px; font-weight: 800; color: #94a3b8;">Deuda actual: <span style="font-size: 26px; font-weight: 900; color: #38bdf8;">S/ {d["monto"]}</span></div>'
                    '</div>'
                    f'<div class="bank-badge" style="background-color: {info_sbs["color"]}; color: {info_sbs["texto"]};">'
                    f'{info_sbs["nombre"]} • {dias_txt}'
                    '</div>'
                    '</div>'
                )
        else:
            html_bancos_body = (
                '<div style="background: #151e32; border: 2.5px dashed #334155; border-radius: 20px; padding: 40px; text-align: center;">'
                '<div style="font-size: 45px; margin-bottom: 10px;">✅</div>'
                '<h2 style="margin: 0; color: #00e676; font-weight: 900;">NO REGISTRA DEUDAS SBS</h2>'
                '<p style="color: #94a3b8; margin-top: 8px; font-weight: bold; font-size: 16px;">Deuda actual: S/ 0.00 en el sistema financiero.</p>'
                '</div>'
            )

        html_bancos_completo = (
            '<div style="width: 100%; max-width: 590px; margin: 0 auto;">'
            '<div class="total-deuda-banner">'
            '<div>'
            '<div style="font-size: 14px; color: #cbd5e1; font-weight: 900; letter-spacing: 0.5px;">DEUDA SBS / MICROFINANZAS</div>'
            f'<div style="font-size: 30px; font-weight: 900; margin-top: 2px; color: white;">{nombre_live}</div>'
            '</div>'
            '<div style="text-align: right;">'
            '<div style="font-size: 13px; color: #cbd5e1; font-weight: 900;">DEUDA TOTAL</div>'
            f'<div style="font-size: 36px; font-weight: 900; color: #38bdf8;">S/ {total_fmt}</div>'
            '</div>'
            '</div>'
            + html_bancos_body +
            '</div>'
        )
        st.markdown(html_bancos_completo, unsafe_allow_html=True)

    # ------------------ OPCIÓN 4: OTRAS DEUDAS (COMERCIAL / PROTESTOS) ------------------
    if estilo_seleccionado == "4. Otras Deudas":
        lista_vencidos = []
        if vencidos_raw:
            for item in urllib.parse.unquote(vencidos_raw).split("~"):
                partes = item.split("*")
                if len(partes) >= 3:
                    lista_vencidos.append({
                        "acreedor": partes[0],
                        "monto": partes[1],
                        "dias": partes[2]
                    })

        total_venc_soles = 0.0
        for v in lista_vencidos:
            try:
                total_venc_soles += float(v["monto"].replace(",", ""))
            except:
                pass

        total_venc_fmt = f"{total_venc_soles:,.2f}"

        html_vencidos_body = ""
        if lista_vencidos:
            for v in lista_vencidos:
                dias_v = v["dias"]
                dias_v_txt = f"{dias_v} días vencido" if dias_v.isdigit() else "Impago"
                html_vencidos_body += (
                    '<div class="bank-card" style="border: 2.5px solid #ef4444;">'
                    '<div>'
                    f'<div style="font-size: 22px; font-weight: 900; color: #ffffff; margin-bottom: 5px;">⚠️ {v["acreedor"]}</div>'
                    f'<div style="font-size: 15px; font-weight: 800; color: #94a3b8;">Monto vencido: <span style="font-size: 26px; font-weight: 900; color: #ef4444;">S/ {v["monto"]}</span></div>'
                    '</div>'
                    '<div class="bank-badge" style="background-color: #ef4444; color: #ffffff;">'
                    f'VENCIDO • {dias_v_txt}'
                    '</div>'
                    '</div>'
                )
        else:
            html_vencidos_body = (
                '<div style="background: #151e32; border: 2.5px dashed #334155; border-radius: 20px; padding: 40px; text-align: center;">'
                '<div style="font-size: 45px; margin-bottom: 10px;">🛡️</div>'
                '<h2 style="margin: 0; color: #00e676; font-weight: 900;">SIN PROTESTOS NI VENCIDOS</h2>'
                '<p style="color: #94a3b8; margin-top: 8px; font-weight: bold; font-size: 16px;">No registra documentos impagos en cámara de comercio (S/ 0.00).</p>'
                '</div>'
            )

        html_vencidos_completo = (
            '<div style="width: 100%; max-width: 590px; margin: 0 auto;">'
            '<div class="total-vencidos-banner">'
            '<div>'
            '<div style="font-size: 14px; color: #fca5a5; font-weight: 900; letter-spacing: 0.5px;">OTRAS DEUDAS POR REGULARIZAR</div>'
            f'<div style="font-size: 30px; font-weight: 900; margin-top: 2px; color: white;">{nombre_live}</div>'
            '</div>'
            '<div style="text-align: right;">'
            '<div style="font-size: 13px; color: #fca5a5; font-weight: 900;">TOTAL PENDIENTE</div>'
            f'<div style="font-size: 36px; font-weight: 900; color: #fef08a;">S/ {total_venc_fmt}</div>'
            '</div>'
            '</div>'
            + html_vencidos_body +
            '</div>'
        )
        st.markdown(html_vencidos_completo, unsafe_allow_html=True)

    st.stop()


# =========================================================================
# VISTA PRIVADA: TU PANEL DE CONTROL (CONTROL DE LA VENTANA ÚNICA)
# =========================================================================
st.markdown("<h1 style='text-align: center; font-size: 38px; font-weight: 900; color: #38bdf8;'>🎛️ PANEL DE CONTROL (PRIVADO)</h1>", unsafe_allow_html=True)
st.caption("Esta pestaña es tu consola privada. Al pulsar el botón, actualizará la MISMA ventana del Live sin abrir pestañas nuevas.")

uploaded_file = st.file_uploader("📂 Sube aquí el PDF del reporte", type=["pdf"])

detected_nombre = "CLIENTE"
detected_score = 0
detected_deudas = []
detected_vencidos = []

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
        if d_sbs:
            detected_deudas = d_sbs
        if d_venc:
            detected_vencidos = d_venc

col_c1, col_c2 = st.columns(2)
with col_c1:
    nombre_final = st.text_input("Nombre detectado (editable):", value=detected_nombre)
with col_c2:
    score_input = st.number_input("Score detectado (editable):", min_value=0, max_value=999, value=detected_score)

score_val = 0 if score_input == 92 else score_input

col_info1, col_info2 = st.columns(2)
with col_info1:
    if detected_deudas:
        nombres_bancos = ", ".join([f"{d['banco']} (S/ {d['monto']})" for d in detected_deudas])
        st.success(f"🏦 SBS: {len(detected_deudas)} bancos detectados: {nombres_bancos}")
    else:
        st.info("ℹ️ SBS: No registra deudas bancarias (S/ 0.00).")

with col_info2:
    if detected_vencidos:
        nombres_venc = ", ".join([f"{v['acreedor']} (S/ {v['monto']})" for v in detected_vencidos])
        st.warning(f"⚠️ Otras Deudas: {len(detected_vencidos)} detectadas: {nombres_venc}")
    else:
        st.info("ℹ️ Otras Deudas: Sin protestos ni vencidos comerciales (S/ 0.00).")

cadena_deudas = "~".join([f"{d['banco']}*{d['monto']}*{d['calif']}*{d['dias']}" for d in detected_deudas])
bancos_enc = urllib.parse.quote(cadena_deudas)

cadena_vencidos = "~".join([f"{v['acreedor']}*{v['monto']}*{v['dias']}" for v in detected_vencidos])
vencidos_enc = urllib.parse.quote(cadena_vencidos)

nombre_encoded = urllib.parse.quote(nombre_final)
t_now = int(time.time())
url_live_completa = f"https://score-verificador.streamlit.app/?live=1&nombre={nombre_encoded}&score={score_val}&bancos={bancos_enc}&vencidos={vencidos_enc}&t={t_now}"

btn_code = (
    '<!DOCTYPE html><html><head><style>'
    'body { margin: 0; padding: 0; background: transparent; font-family: "Segoe UI", Tahoma, sans-serif; }'
    '.btn-live {'
    '  display: block; width: 100%; border: none; outline: none; cursor: pointer;'
    '  background: linear-gradient(90deg, #2563eb, #00e676);'
    '  color: #ffffff; text-align: center;'
    '  padding: 16px 20px; font-size: 18px; font-weight: 900;'
    '  border-radius: 14px; text-decoration: none;'
    '  box-shadow: 0 6px 20px rgba(37,99,235,0.4);'
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
