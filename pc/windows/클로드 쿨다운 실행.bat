@echo off
chcp 65001 >nul
rem 클로드 쿨다운 실행 - 검은 창 없이 위젯과 트레이 아이콘을 띄운다
cd /d "%~dp0"

rem 필요한 것이 다 깔려 있는지 먼저 본다.
rem pythonw 로 바로 띄우면 실패해도 오류창도 콘솔도 안 뜨고 그냥 아무 일이 없다.
python -c "import requests, PIL, pystray" 2>nul
if errorlevel 1 goto missing

start "" pythonw "%~dp0cooldown_app.py"
exit /b 0

:missing
echo.
echo   실행에 필요한 것이 아직 안 깔렸습니다.
echo   아래 한 줄을 실행한 뒤 다시 눌러 주세요.
echo.
echo       pip install -r "%~dp0..\requirements.txt"
echo.
pause
exit /b 1
