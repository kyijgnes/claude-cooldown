@echo off
cd /d "%~dp0"

rem Prefer python; fall back to the py launcher if python is not on PATH.
set "PY=python"
where python >nul 2>nul || set "PY=py -3"

echo ================================
echo   Claude Cooldown - build exe
echo ================================
echo.

echo [1/2] Ensuring PyInstaller is installed...
%PY% -m pip install --disable-pip-version-check pyinstaller
if errorlevel 1 goto fail

echo.
echo [2/2] Building (Korean status messages below come from build_exe.py)...
%PY% build_exe.py
if errorlevel 1 goto fail

echo.
echo Build finished. See "dist" folder above for the exe path.
echo.
pause
exit /b 0

:fail
echo.
echo *** Build FAILED - read the messages above. Python must be installed. ***
echo.
pause
exit /b 1
