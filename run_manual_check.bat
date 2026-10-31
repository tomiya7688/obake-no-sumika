@echo off
setlocal
cd /d "%~dp0"

rem Opens the real-screen check window (tools/manual_check). It uses the
rem project .venv, which run_editor.bat and run_object_editor.bat prepare.
rem Keep this file ASCII with CRLF line endings: cmd.exe misreads LF-only or
rem UTF-8 batch files.
if not exist ".venv\Scripts\python.exe" (
    echo The project environment is not ready yet.
    echo Start run_object_editor.bat once, then run this file again.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -B "tools\manual_check\script\manual_check.py"
if errorlevel 1 (
    echo.
    echo The check window could not open. Please show the message above to the agent.
    pause
    exit /b 1
)
exit /b 0
