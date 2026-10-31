import streamlit as st
import pdfplumber
import re

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
    if re.search(r'excluid[oa]|código\s+de\s+exclusión|codigo\s+de\s+exclusion', texto_p1, re.IGNORECASE):
        return 0

    m1 = re.search(r'Score\s+Experian[^\d]{0,40}?(\b[1-9]\d{2}\b)', texto_p1, re.IGNORECASE)
    if m1:
        s = int(m1.group(1))
        return 0 if s == 92 else s

    m2 = re.search(r'(\b[1-9]\d{2}\b)[\s\n]*(?:Puntaje\s*(?:Excelente|Buen|Medio|Bajo|Muy\s*Bajo))', texto_p1, re.IGNORECASE)
    if m2:
        s = int(m2.group(1))
        return 0 if s == 92 else s

    m3 = re.search(r'(?:Puntaje\s*(?:Excelente|Buen|Medio|Bajo|Muy\s*Bajo))[\s\n]*(\b[1-9]\d{2}\b)', texto_p1, re.IGNORECASE)
    if m3:
        s = int(m3.group
