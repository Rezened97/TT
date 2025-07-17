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