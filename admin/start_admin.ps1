$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$env:PYTHONPATH = "backend;admin"

.\.venv\Scripts\python.exe -m uvicorn admin.app.main:app --host 0.0.0.0 --port 8002
