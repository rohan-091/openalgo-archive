# OpenAlgo PowerShell Launcher
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "Starting OpenAlgo Trading Platform..." -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERROR] Virtual environment (.venv) not found!" -ForegroundColor Red
    Write-Host "Run 'uv sync' first to set up the environment." -ForegroundColor Yellow
    exit 1
}

& $pythonExe (Join-Path $PSScriptRoot "app.py")
