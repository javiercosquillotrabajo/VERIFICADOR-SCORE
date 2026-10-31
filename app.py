import streamlit as st
import pdfplumber
import re

# Configuración de página
st.set_page_config(
    page_title="Verificación de Score",
    page_icon="💳",
    layout="wide"
)

# Estilos CSS adaptados al diseño oscuro
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
        position: relative;
    }
    .circle-score {
        font-size: 65px;
        font-weight: 800;
        line-height: 1;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

# Escala de Scores
RANGOS = [
    {"label": "Excelente Puntaje", "min": 877, "max": 999, "color": "#00c875"},
    {"label": "Buen Puntaje",      "min": 722, "max": 876, "color": "#1db954"},
    {"label": "Puntaje Medio",     "min": 598, "max": 721, "color": "#f59e0b"},
    {"label": "Puntaje Bajo",      "min": 477, "max": 597, "color": "#e67e22"},
    {"label": "Puntaje Muy Bajo",  "min": 1,   "max": 476, "color": "#e74c3c"},
]

def clasificar_score(score):
    for r in RANGOS:
        if r["min"] <= score <= r["max"]:
            return r
    return RANGOS[-1]

def procesar_pdf(file):
    texto = ""
    with pdfplumber.open(file) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                texto += t + "\n"

    # Extracción de Nombre
    nombre = "CLIENTE"
    match_nombre = re.search(r'(?:NOMBRE|TITULAR|RAZÓN SOCIAL)[:\s]+([A-ZÁÉÍÓÚÑ\s]{4,35})', texto, re.IGNORECASE)
    if match_nombre:
        nombre = match_nombre.group(1).strip().split()[0].upper()
    else:
        palabras = re.findall(r'\b[A-ZÁÉÍÓÚÑ]{4,}\b', texto)
        if palabras:
            nombre = palabras[0].upper()

    # Extracción de Score
    score = None
    match_score = re.search(r'(?:score|puntaje|calificación|calificacion)[^\d]{1,25}(\d{2,3})', texto, re.IGNORECASE)
    if match_score:
        score = int(match_score.group(1))
    else:
        candidatos = re.findall(r'\b([1-9]\d{2})\b', texto)
        if candidatos:
            score = int(candidatos[0])

    return nombre, score, texto

# --- CABECERA ---
st.markdown("<h1 style='text-align: center; color: white; margin-bottom: 30px;'>VERIFICACIÓN DE SCORE CREDITICIO</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Adjunta el PDF del reporte Experian / Equifax", type=["pdf"])

if uploaded_file:
    nombre, score, texto_completo = procesar_pdf(uploaded_file)

    col_input1, col_input2 = st.columns(2)
    with col_input1:
        nombre_final = st.text_input("Nombre detectado:", value=nombre)
    with col_input2:
        score_final = st.number_input("Score detectado:", min_value=1, max_value=999, value=score if score else 550)

    categoria = clasificar_score(score_final)

    st.markdown("---")

    # --- PANTALLA PRINCIPAL: DOS COLUMNAS ---
    col_izq, col_der = st.columns([1, 1], gap="large")

    # Columna Izquierda: Tarjetas de Score
    with col_izq:
        st.markdown("<div style='background: #111a2d; padding: 25px; border-radius: 15px;'>", unsafe_allow_html=True)
        st.markdown("### Score Crediticio")
        st.caption("Es un número que indica la probabilidad de cumplir con tus obligaciones financieras.")
        st.write("")

        for r in RANGOS:
            activo = (r["label"] == categoria["label"])
            clase = "tier-active" if activo else ""
            borde = f"border: 2.5px solid {r['color']};" if activo else "border: 1px solid rgba(255,255,255,0.05);"

            st.markdown(f"""
            <div class="tier-card {clase}" style="background-color: {r['color']}; {borde}">
                <span style="color: white;">Score: {r['min']} - {r['max']}</span>
                <span style="color: white;">{r['label']}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # Columna Derecha: Círculo y Saludo
    with col_der:
        st.markdown("<div style='background: #111a2d; padding: 25px; border-radius: 15px; text-align: center;'>", unsafe_allow_html=True)
        st.markdown(f"<h1 style='color: white; margin: 0;'>¡Hola {nombre_final}!</h1>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color: {categoria['color']}; margin-top: 5px;'>Tu Score es {categoria['label'].replace('Puntaje ', '')}</h2>", unsafe_allow_html=True)

        # Círculo del Score
        st.markdown(f"""
        <div class="circle-container" style="border: 14px solid {categoria['color']};">
            <span style="color: #94a3b8; font-size: 15px;">Tu score es</span>
            <span class="circle-score" style="color: white;">{score_final}</span>
            <span style="color: #94a3b8; font-size: 15px;">de 999</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"<h4 style='color: {categoria['color']}; font-weight: bold;'>● Verificado</h4>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

else:
    st.info("👆 Por favor sube un PDF para generar la ficha de score.")
