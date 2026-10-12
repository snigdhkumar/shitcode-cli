@echo off
title ShitCode Local Client Agent
cd /d "%~dp0"

python -c "import websockets, httpx, bs4" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ShitCode] Installing required dependencies...
    python -m pip install -q -r requirements.txt
)

python shitcode.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Client exited with error code %ERRORLEVEL%.
    pause
)
