@echo off
REM ── Vai nella cartella corrente del .bat
cd /d "%~dp0"

REM ── Lancia PowerShell in bypass mode; rimane aperto solo se fallisce
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "Set-ExecutionPolicy Bypass -Scope Process -Force; .\setup.ps1; if (\$LASTEXITCODE -ne 0) { pause }"

pause

