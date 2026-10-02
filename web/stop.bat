@echo off
echo ==================================================
echo   DUNG SERVER
echo ==================================================
REM Stop only the server recorded by app.py, never every python.exe.
set "PID_FILE=%~dp0server.pid"
if exist "%PID_FILE%" (
    set /p SERVER_PID=<"%PID_FILE%"
    call taskkill /f /t /pid %%SERVER_PID%% 2>nul
    del "%PID_FILE%" 2>nul
) else (
    echo [INFO] Khong thay server.pid - server khong chay hoac da dung.
)
taskkill /f /im cloudflared.exe 2>nul
echo [OK] Da dung
