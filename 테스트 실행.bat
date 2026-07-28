@echo off
cd /d "%~dp0windows"

rem TEST launcher: runs the app from source with a VISIBLE console so that
rem errors, tracebacks and ping activity are shown while testing.
rem (The silent launcher is the pythonw .bat inside this windows folder.)

set "PY=python"
where python >nul 2>nul || set "PY=py -3"

echo ============================================
echo   Claude Cooldown - TEST run (console shown)
echo ============================================
echo NOTE: if a widget is already running, quit it first
echo       (tray icon ^> exit), or this just summons it and exits.
echo.

%PY% -c "import requests, PIL, pystray" 2>nul
if errorlevel 1 goto missing

%PY% cooldown_app.py
echo.
echo (app closed - exit code %errorlevel%)
pause
exit /b 0

:missing
echo.
echo Missing dependencies. Run this once, then retry:
echo     %PY% -m pip install -r "..\requirements.txt"
echo.
pause
exit /b 1
