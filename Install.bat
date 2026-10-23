@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" %*
if errorlevel 1 (echo Instalasi gagal. Baca pesan di atas.) else (echo Instalasi selesai. Jalankan Start.bat.)
pause
