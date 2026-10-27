@echo off
setlocal
cd /d "%~dp0"

if exist ".venv-setup.lock" goto :base_python
if exist ".venv\Scripts\python.exe" goto :existing_venv

:base_python
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

%PYTHON_CMD% -I -B "tools\security\script\launch.py" conversation-editor
if errorlevel 1 goto :error
exit /b 0

:existing_venv
".venv\Scripts\python.exe" -I -B "tools\security\script\launch.py" conversation-editor
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo The application could not start. See tools/security/README.md for recovery steps.
pause
exit /b 1
