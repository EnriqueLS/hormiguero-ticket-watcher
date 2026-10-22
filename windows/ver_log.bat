@echo off
cd /d "%~dp0.."
if not exist "datos\vigilante.log" (echo Todavia no hay log. & pause & exit /b)
powershell -NoProfile -Command "Get-Content -Path datos\vigilante.log -Tail 40 -Wait -Encoding UTF8"
