@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0sync-skills.ps1" %*
pause
