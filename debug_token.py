# debug_token.py

import os
from dotenv import load_dotenv
import requests

# 1) Carica .env
load_dotenv()

# 2) Prendi token e credenziali
token = os.getenv("META_ACCESS_TOKEN")
app_id = os.getenv("APP_ID")
app_secret = os.getenv("APP_SECRET")

# 3) Chiama /debug_token con app access token (app_id|app_secret)
resp = requests.get(
    "https://graph.facebook.com/debug_token",
    params={
        "input_token": token,
        "access_token": f"{app_id}|{app_secret}"
    }
).json()

# 4) Stampa il risultato
print(resp)
