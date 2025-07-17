import os
import streamlit as st

# Carica le impostazioni da Streamlit secrets o variabili d'ambiente
API_VERSION = st.secrets.get("API_VERSION") or os.getenv("API_VERSION")
AD_ACCOUNT_ID = st.secrets.get("AD_ACCOUNT_ID") or os.getenv("AD_ACCOUNT_ID")
APP_ID = st.secrets.get("APP_ID") or os.getenv("APP_ID")
APP_SECRET = st.secrets.get("APP_SECRET") or os.getenv("APP_SECRET")
ACCESS_TOKEN = st.secrets.get("ACCESS_TOKEN") or os.getenv("ACCESS_TOKEN")
FB_BUSINESS_ID = st.secrets.get("FB_BUSINESS_ID") or os.getenv("FB_BUSINESS_ID")
PIXEL_ID = st.secrets.get("PIXEL_ID") or os.getenv("PIXEL_ID")

# Verifica che tutte le variabili siano presenti
missing = [
    var for var in [
        "API_VERSION", "AD_ACCOUNT_ID", "PIXEL_ID",
        "APP_ID", "APP_SECRET",
        "ACCESS_TOKEN", "FB_BUSINESS_ID"
    ]
    if not globals().get(var)
]
if missing:
    raise ValueError(
        f"Mancano le seguenti variabili di configurazione: {', '.join(missing)}"
    )
