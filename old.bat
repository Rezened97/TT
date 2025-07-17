@echo off
cd /d %~dp0

REM Imposta la cartella corrente (AdLaunch) come PYTHONPATH
set PYTHONPATH=%cd%

REM Avvia Streamlit con il venv
.venv\Scripts\python.exe -m streamlit run app.py

pause