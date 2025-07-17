<#
.SYNOPSIS
  Crea/usa venv, installa dipendenze nel venv e avvia Streamlit.
#>
Param()

# --- 0) Percorsi base ---
$root        = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir     = Join-Path  $root 'venv'
$venvPython  = Join-Path  $venvDir 'Scripts\python.exe'
$requirements= Join-Path  $root   'requirements.txt'

# --- 1) Trova o installa global Python3 ---
function Test-Python3 { param($c) try { (& $c --version) -match '^Python\s+3\.' } catch { $false } }
$py = @('python','python3','py') | Where-Object { Test-Python3 $_ } | Select-Object -First 1
if (-not $py) {
    Write-Host "Python3 non trovato. Provo con winget/choco..."
    if (Get-Command winget -ErrorAction SilentlyContinue) { winget install --id Python.Python.3 -e --silent }
    elseif (Get-Command choco -ErrorAction SilentlyContinue) { choco install python -y }
    else { Write-Error "Installa Python3 da https://python.org/downloads/windows/"; exit 1 }
    Write-Host "Rilancio script..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath; exit 0
}
Write-Host "Usando Python globale: $py"

# --- 2) Crea il venv se manca ---
if (-not (Test-Path $venvPython)) {
    Write-Host "Creo virtualenv in `$venvDir`..."
    & $py -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { Write-Error "Creazione venv fallita."; exit 1 }
}
if (-not (Test-Path $venvPython)) {
    Write-Error "Non trovo `$venvPython` dopo creazione venv."; exit 1
}

# --- 3) Assicuro pip nel venv e installo dipendenze ---
Write-Host "Assicuro pip con ensurepip..."
& $venvPython -m ensurepip --upgrade

Write-Host "Installazione requirements..."
& $venvPython -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) {
    Write-Error "Installazione dipendenze fallita."
    Read-Host "Premi INVIO per uscire..."
    exit 1
}

# --- 4) Avvia Streamlit col python del venv ---
Write-Host "Avvio Streamlit..."
Start-Process -FilePath $venvPython -ArgumentList @(
    '-m','streamlit','run',
    "$root\app.py",
    '--server.headless=true',
    '--server.port=8501',
    '--server.address=127.0.0.1'
) -WorkingDirectory $root

# --- 5) Apro il browser ---
Start-Sleep -Seconds 5
Start-Process 'http://127.0.0.1:8501'

exit 0
