$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "C:\Python314\python.exe"
}
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8001 --reload
