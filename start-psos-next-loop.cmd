@echo off
cd /d "%~dp0"
start "PSOS next-loop" powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-psos-next-loop.ps1"
exit /b 0
