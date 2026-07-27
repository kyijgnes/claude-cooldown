@echo off
rem 클로드 쿨다운 실행 - 검은 창 없이 위젯과 트레이 아이콘을 띄운다
cd /d "%~dp0"
start "" pythonw "%~dp0cooldown_app.py"
