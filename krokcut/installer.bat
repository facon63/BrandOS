@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Installation de KrokCut ===

where python >nul 2>nul
if errorlevel 1 (
  echo Python est introuvable. Installe Python 3.11 ou 3.12 depuis https://www.python.org/downloads/
  echo IMPORTANT : coche "Add python.exe to PATH" pendant l'installation, puis relance ce fichier.
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg est introuvable. Installation via winget...
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  echo Ferme cette fenetre et relance installer.bat pour que ffmpeg soit pris en compte.
  pause
  exit /b 1
)

python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo L'installation des dependances a echoue.
  pause
  exit /b 1
)
echo.
echo Installation terminee ! Double-clique sur lancer.bat pour ouvrir KrokCut.
pause
