@echo off
echo ==================================================
echo   DUNG SERVER
echo ==================================================
taskkill /f /im python.exe 2>nul
taskkill /f /im cloudflared.exe 2>nul
echo [OK] Da dung tat ca
