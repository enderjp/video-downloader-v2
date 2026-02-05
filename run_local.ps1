param(
    [string]$ChromeBin
)

Write-Host "== run_local.ps1: iniciar entorno local para video-downloader-v2 =="

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Error "No se encontró el lanzador 'py'. Asegúrate de tener Python instalado en Windows (https://www.python.org/downloads/)."
    exit 1
}

# Crear venv si no existe
if (-not (Test-Path -Path .\.venv)) {
    Write-Host "Creando virtualenv .venv..."
    py -3 -m venv .venv
} else {
    Write-Host "Virtualenv .venv ya existe"
}

Write-Host "Activando virtualenv..."
.\.venv\Scripts\Activate.ps1

Write-Host "Actualizando pip e instalando dependencias..."
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

if ($ChromeBin) {
    Write-Host "Usando CHROME_BIN=$ChromeBin"
    $env:CHROME_BIN = $ChromeBin
} else {
    Write-Host "No se ha especificado CHROME_BIN. Asegúrate de que Chrome/Chromium esté instalado y en PATH."
}

Write-Host "Iniciando uvicorn (main_selenium:app) en http://0.0.0.0:8001..."
py -3 -m uvicorn main_selenium:app --reload --host 0.0.0.0 --port 8001
