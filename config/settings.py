# config/settings.py

import os
from dotenv import load_dotenv

# Carica il file .env
load_dotenv()

# Versione dell'API Graph (se vuoi, cambia qui)
API_VERSION = os.getenv("API_VERSION", "v19.0")

# AD_ACCOUNT_ID senza prefisso "act_"
AD_ACCOUNT_ID = os.getenv("AD_ACCOUNT_ID")
if not AD_ACCOUNT_ID:
    raise ValueError("AD_ACCOUNT_ID mancante in .env")

# Pixel ID
PIXEL_ID = os.getenv("PIXEL_ID")
if not PIXEL_ID:
    raise ValueError("PIXEL_ID mancante in .env")

[credentials]
# username = "password"
DanyR   = "Password123"
luca    = "secret456"
anna    = "mypassword"






import os
import streamlit as st

# Carica le impostazioni da Streamlit secrets o da variabili d'ambiente come fallback

# Versione API di Meta Graph
API_VERSION = st.secrets.get("API_VERSION") or os.getenv("API_VERSION")
# ID dell'account pubblicitario (senza "act_")
AD_ACCOUNT_ID = st.secrets.get("AD_ACCOUNT_ID") or os.getenv("AD_ACCOUNT_ID")
# Credenziali Facebook
APP_ID = st.secrets.get("APP_ID") or os.getenv("APP_ID")
APP_SECRET = st.secrets.get("APP_SECRET") or os.getenv("APP_SECRET")
ACCESS_TOKEN = st.secrets.get("ACCESS_TOKEN") or os.getenv("ACCESS_TOKEN")
# Business ID
FB_BUSINESS_ID = st.secrets.get("FB_BUSINESS_ID") or os.getenv("FB_BUSINESS_ID")

# Controllo valori minimi
missing = []
for var_name in ["API_VERSION", "AD_ACCOUNT_ID", "APP_ID", "APP_SECRET", "ACCESS_TOKEN", "FB_BUSINESS_ID"]:
    if not globals()[var_name]:
        missing.append(var_name)

if missing:
    raise ValueError(f"Mancano le seguenti variabili di configurazione: {', '.join(missing)}")
