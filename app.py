import streamlit as st
import pdfplumber
import re

st.set_page_config(
    page_title="Verificación de Score",
    page_icon="💳",
    layout="wide"
)

# Estilos CSS
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
    with pdfplu
