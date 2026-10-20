# run_sidecar.ps1 — Start the Videogrammetry Sidecar on port 8001
#
# WHAT THIS DOES:
#   Launches the independent Videogrammetry Sidecar service on http://127.0.0.1:8001
#   Zero impact or modification to host project backend running on port 8000.
#
# USAGE:
#   .\.venv\Scripts\python.exe videogrammetry\run_sidecar.py

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host ""
Write-Host "=== Starting Videogrammetry Sidecar Service ===" -ForegroundColor Cyan
Write-Host "  URL:   http://127.0.0.1:8001" -ForegroundColor Green
Write-Host "  Docs:  http://127.0.0.1:8001/docs" -ForegroundColor Yellow
Write-Host ""

& .\.venv\Scripts\python.exe videogrammetry\run_sidecar.py
