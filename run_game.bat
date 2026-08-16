@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3 was not found. Install Python, then run this file again.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
) else (
    set "PYTHON_CMD=py"
)

if not exist ".venv\Scripts\python.exe" (
    echo Preparing the game for its first launch...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo Installing pygame...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" game.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo The game could not start. See README.md for manual setup steps.
pause
exit /b 1
