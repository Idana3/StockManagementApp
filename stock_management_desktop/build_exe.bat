@echo off
cd /d "%~dp0"
if not exist build mkdir build
if not exist dist mkdir dist
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onefile ^
  --name StockManagementApp ^
  --icon assets\app_icon.ico ^
  --add-data "assets;assets" ^
  --version-file version_info.txt ^
  main.py
pause
