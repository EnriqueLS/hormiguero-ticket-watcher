@echo off
cd /d "%~dp0.."
start "" ".venv\Scripts\pythonw.exe" "src\vigilante.py" --continuo
echo Vigilante arrancado en segundo plano.
pause
