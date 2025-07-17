# token_manager.py

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import os
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv()

class TokenManager:
    def __init__(self):
        self.access_token = os.getenv("META_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("META_ACCESS_TOKEN non trovato nel file .env")

    def get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
