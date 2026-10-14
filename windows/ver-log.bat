@echo off
powershell -NoProfile -Command "Get-Content -Path '%~dp0..\logs\vigilante.log' -Tail 40 -Wait -Encoding UTF8"
