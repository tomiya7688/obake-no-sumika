@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

rem Opens the real-screen check window (tools/manual_check). It uses the
rem project's .venv, which run_editor.bat / run_object_editor.bat prepare.
if not exist ".venv\Scripts\python.exe" (
    echo 先に run_object_editor.bat を一度起動して、準備を済ませてください。
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -B "tools\manual_check\script\manual_check.py"
if errorlevel 1 (
    echo.
    echo 確認画面を開けませんでした。上のメッセージをエージェントに伝えてください。
    pause
    exit /b 1
)
exit /b 0
