import streamlit as st
import pdfplumber
import re

st.set_page_config(
    page_title="Verificación de Score",
    page_icon="💳",
    layout="wide"
)

# Estilos visuales acordes a tu diseño
st.markdown("""
<style>
    .stApp {
        background-color: #0b111e;
        color: #ffffff;
    }
    .tier-card {
        padding: 14px 18px;
        border-radius: 10px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-family: sans-serif;
        font-weight: 600;
        font-size: 15px;
        opacity: 0.35;
        transition: all 0.3s ease;
    }
    .tier-active {
        opacity: 1 !important;
        transform: scale(1.03);
        box-shadow: 0px 0px 20px rgba(255, 255, 255, 0.25);
    }
    .circle-container {
        width: 250px;
        height: 250px;
        border-radius: 50%;
        margin: 30px auto 20px auto;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        background: #131c2e;
    }
    .circle-score {
        font-size: 65px;
        font-weight: 800;
        line-height: 1;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

RANGOS = [
    {"label": "Excelente Puntaje", "min": 877, "max": 999, "color": "#00c875", "rango_texto": "877 - 999"},
    {"label": "Buen Puntaje",      "min": 722, "max": 876, "color": "#1db954", "rango_texto": "722 - 876"},
    {"label": "Puntaje Medio",     "min": 598, "max": 721, "color": "#f59e0b", "rango_texto": "598 - 721"},
    {"label": "Puntaje Bajo",      "min": 477, "max": 597, "color": "#e67e22", "rango_texto": "477 - 597"},
    {"label": "Puntaje Muy Bajo",  "min": 0,   "max": 476, "color": "#e74c3c", "rango_texto": "0 - 476"},
]

def clasificar_score(score):
    for r in RANGOS:
        if r["min"] <= score <= r["max"]:
            return r
    return RANGOS[-1]

def extraer_score_experian(pagina):
    """Busca el puntaje exclusivamente dentro de la zona del termómetro en la página 1."""
    texto_p1 = pagina.extract_text() or ""

    # Método 1: Al lado de "Score Experian"
    m1 = re.search(r'Score\s+Experian[^\d]{0,40}?(\b[1-9]\d{2}\b)', texto_p1, re.IGNORECASE)
    if m1:
        return int(m1.group(1))

    # Método 2: Número de 3 dígitos antes o después de "Puntaje (Bajo|Medio|Buen|Excelente)"
    m2 = re.search(r'(\b[1-9]\d{2}\b)[\s\n]*(?:Puntaje\s*(?:Excelente|Buen|Medio|Bajo|Muy\s*Bajo))', texto_p1, re.IGNORECASE)
    if m2:
        return int(m2.group(1))

    m3 = re.search(r'(?:Puntaje\s*(?:Excelente|Buen|Medio|Bajo|Muy\s*Bajo))[\s\n]*(\b[1-9]\d{2}\b)', texto_p1, re.IGNORECASE)
    if m3:
        return int(m3.group(1))

    # Método 3: Búsqueda espacial por coordenadas (cuadrante superior derecho del recuadro azul)
    ancho = pagina.width
    palabras = pagina.extract_words()
    candidatos = []
    for w in palabras:
        t = w['text'].strip()
        # Números enteros de 3 dígitos en la mitad derecha
        if t.isdigit() and len(t) == 3 and w['x0'] > (ancho * 0.5):
            candidatos.append((w['top'], int(t)))

    if candidatos:
        candidatos.sort(key=lambda x: x[0])  # Toma el que esté más arriba (el del recuadro azul superior)
        return candidatos[0][1]

    return None

def extraer_nombre(pdf):
    """Extrae el nombre de la persona priorizando la fila de nombres o la cabecera del DNI."""
    texto_completo = ""
    for pag in pdf.pages[:2]:  # Revisa página 1 y 2
        t = pag.extract_text()
        if t:
            texto_completo += t + "\n"

    # Caso A: De la cabecera "DNI 42592619 - COSQUILLO CALIXTO JAVIER AUGUSTO"
    match_cabecera = re.search(r'DNI\s+\d{8}\s*-\s*([A-ZÁÉÍÓÚÑ\s]+)', texto_completo)
    if match_cabecera:
        palabras_cab = [p for p in match_cabecera.group(1).split() if len(p) > 2]
        if len(palabras_cab) >= 3:
            # Si tiene Apellido1 Apellido2 Nombre1... extrae el primer nombre (3ra palabra)
            return palabras_cab[2].upper()
        elif palabras_cab:
            return palabras_cab[-1].upper()

    # Caso B: De la fila "Nombres" en Datos Personales
    lineas = texto_completo.splitlines()
    palabras_a_ignorar = {'NOMBRES', 'NOMBRE', 'DATOS', 'PERSONALES', 'APELLIDOS', 'APELLIDO', 'DNI'}
    for i, linea in enumerate(lineas):
        if re.search(r'\bNOMBRES?\b', linea, re.IGNORECASE):
            texto_fila = linea + (" " + lineas[i+1] if i+1 < len(lineas) else "")
            palabras = [p for p in re.findall(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]+', texto_fila) if p.upper() not in palabras_a_ignorar and len(p) > 1]
            if palabras:
                return palabras[-1].upper()

    return "CLIENTE"

# --- INTERFAZ ---
st.markdown("<h1 style='text-align: center; color: white; margin-bottom: 30px;'>VERIFICACIÓN DE SCORE CREDITICIO</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Adjunta el PDF del reporte Experian / Equifax", type=["pdf"])

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        pag1 = pdf.pages[0]
        score_detectado = extraer_score_experian(pag1)
        nombre_detectado = extraer_nombre(pdf)

    # Permitir ajuste manual si fuera necesario
    valor_inicial = score_detectado if score_detectado is not None else 550

    col_input1, col_input2 = st.columns(2)
    with col_input1:
        nombre_final = st.text_input("Nombre detectado:", value=nombre_detectado)
    with col_input2:
        score_input = st.number_input("Score detectado:", min_value=0, max_value=999, value=valor_inicial)

    categoria = clasificar_score(score_input)

    st.markdown("---")

    col_izq, col_der = st.columns([1, 1], gap="large")

    # Columna izquierda: Escala de colores
    with col_izq:
        st.markdown("<div style='background: #111a2d; padding: 25px; border-radius: 15px;'>", unsafe_allow_html=True)
        st.markdown("### Score Crediticio")
        st.caption("Es un número que indica la probabilidad de cumplir con tus obligaciones financieras.")
        st.write("")

        for r in RANGOS:
            activo = (r["label"] == categoria["label"])
            clase = "tier-active" if activo else ""
            borde = f"border: 2.5px solid {r['color']};" if activo else "border: 1px solid rgba(255,255,255,0.05);"

            html_box = f"""
            <div class="tier-card {clase}" style="background-color: {r['color']}; {borde}">
                <span style="color: white;">Score: {r['rango_texto']}</span>
                <span style="color: white;">{r['label']}</span>
            </div>
            """
            st.markdown(html_box, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # Columna derecha: Saludo y velocímetro
    with col_der:
        st.markdown("<div style='background: #111a2d; padding: 25px; border-radius: 15px; text-align: center;'>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='color: white; margin: 0;'>¡Hola {nombre_final}!</h1>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color: {categoria['color']}; margin-top: 5px;'>Tu Score es {categoria['label'].replace('Puntaje ', '')}</h2>", unsafe_allow_html=True)

        html_circle = f"""
        <div class="circle-container" style="border: 14px solid {categoria['color']};">
            <span style="color: #94a3b8; font-size: 15px;">Tu score es</span>
            <span class="circle-score" style="color: white;">{score_input}</span>
            <span style="color: #94a3b8; font-size: 15px;">de 999</span>
        </div>
        """
        st.markdown(html_circle, unsafe_allow_html=True)

        st.markdown(f"<h4 style='color: {categoria['color']}; font-weight: bold;'>● Verificado</h4>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

else:
    st.info("👆 Por favor sube un PDF para generar la ficha de score.")
