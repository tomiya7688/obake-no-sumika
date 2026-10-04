@echo off
setlocal
set "SUMIKA_GODOT=%~1"
if not defined SUMIKA_GODOT set "SUMIKA_GODOT=%GODOT_BIN%"
if not defined SUMIKA_GODOT for /f "delims=" %%G in ('where godot.exe 2^>nul') do if not defined SUMIKA_GODOT set "SUMIKA_GODOT=%%G"
if not defined SUMIKA_GODOT (
  echo Godot 4 executable not found. Set GODOT_BIN or pass its full path:
  echo run_godot.bat "C:\path\Godot_win64.exe"
  pause
  exit /b 1
)
"%SUMIKA_GODOT%" --path "%~dp0godot"
exit /b %errorlevel%
