@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
  echo Lance d'abord installer.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m krokcut serve
pause
