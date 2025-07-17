# ui/interface.py

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import traceback

# Il minimo indispensabile per testare input e button
try:
    st.set_page_config(page_title="AdLaunch Test", layout="wide")
except Exception:
    # se era già stato chiamato in app.py, ignoriamo
    pass

st.title("🚩 INTERFACCIA DI TEST")

# Un campo di testo semplice
name = st.text_input("Digita qualcosa qui:", key="test_name")

# Un bottone che stampa il contenuto del campo
if st.button("📤 Invia"):
    st.write(f"Hai scritto: **{name}**")

# Bottone di diagnostica
if st.button("🔍 Show session_state"):
    st.write(st.session_state)

# Cattura ogni errore fatale
try:
    pass
except Exception:
    st.error("❌ Errore fatale nell'interfaccia di test:")
    st.text(traceback.format_exc())
