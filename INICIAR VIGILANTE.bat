@echo off
title Vigilante El Hormiguero (cierra esta ventana para pararlo)
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto instalar
if not exist ".env" goto instalar
goto lanzar
:instalar
echo Primera vez: instalando...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\instalar.ps1" -SinPausa
if errorlevel 1 (pause & exit /b 1)
:lanzar
echo.
echo  Vigilante El Hormiguero funcionando. Revisa la web cada minuto.
echo  Para PARARLO: cierra esta ventana.
echo.
".venv\Scripts\python.exe" "src\vigilante.py" --continuo
echo.
echo El vigilante se ha detenido.
pause
