@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Jalankan Install.bat terlebih dahulu.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" scripts\launch.py
pause
