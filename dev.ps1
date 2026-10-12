# dev.ps1 — Start the backend with hot-reload that does NOT watch upload/output dirs.
#
# WHAT THIS DOES:
#   Runs uvicorn with --reload but restricts the file watcher to only backend/ and
#   pipeline/ source code directories. Without this, writing uploaded videos or
#   reconstruction output to output/ triggers the watcher, which instantly reboots
#   the server and kills any running 3D reconstruction mid-flight.
#
# USAGE:
#   .\.venv\Scripts\python.exe dev.ps1
#   — or —
#   .\dev.ps1           (if .venv is activated)

$ErrorActionPreference = "Stop"

# Ensure we run from the project root
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "=== Spatial Twin Backend (dev mode) ===" -ForegroundColor Cyan
Write-Host "  Reload watches: backend/, pipeline/ only" -ForegroundColor DarkGray
Write-Host "  Excluded:       output/, static/, data/, .venv/, scratch/" -ForegroundColor DarkGray
Write-Host ""

& .\.venv\Scripts\python.exe -m uvicorn backend.main:app `
    --host 127.0.0.1 `
    --port 8000 `
    --reload `
    --reload-dir backend `
    --reload-dir pipeline
