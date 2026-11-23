@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo Starting OpenAlgo Trading Platform...
echo ===================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment (.venv) not found!
    echo Run 'uv sync' first to set up the environment.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" app.py
pause
