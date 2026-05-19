@echo off
cd /d "%~dp0"

if not exist dist\StockManagementApp.exe (
  echo StockManagementApp.exe was not found in the dist folder.
  echo Run build_exe.bat first, then run this installer build.
  pause
  exit /b 1
)

where iscc >nul 2>nul
if errorlevel 1 (
  echo Inno Setup Compiler was not found on PATH.
  echo Install Inno Setup, then run this script again.
  echo Download: https://jrsoftware.org/isinfo.php
  pause
  exit /b 1
)

iscc installer.iss
pause
