@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" conversation_editor.py
    exit /b 0
)

where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw conversation_editor.py
    exit /b 0
)

where py >nul 2>nul
if not errorlevel 1 (
    py conversation_editor.py
    exit /b %errorlevel%
)

echo Python 3 was not found. Install Python, then run this file again.
pause
exit /b 1
