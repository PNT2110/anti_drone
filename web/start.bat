@echo off
echo ==================================================
echo   HE THONG PHAT HIEN DRONE - KHOI DONG
echo ==================================================
echo.

REM The tunnel publishes this server on the internet, so a password is mandatory.
if "%ANTI_DRONE_PASSWORD%"=="" (
    echo [LOI] Chua dat mat khau. Chay lenh sau roi thu lai:
    echo         set ANTI_DRONE_PASSWORD=mat-khau-cua-ban
    exit /b 1
)

cd /d "%~dp0"

REM Start web server in background
echo [1/2] Khoi dong web server...
start /B python app.py > server.log 2>&1
timeout /t 5 /nobreak > nul

REM Start cloudflared tunnel
echo [2/2] Tao link cong khai...
echo.
echo ===================================================
echo   Dang cho link cong khai...
echo   Dang nhap: ten bat ky + mat khau ANTI_DRONE_PASSWORD
echo   Dung Ctrl+C de dung tunnel, stop.bat de dung server
echo ===================================================
echo.
cloudflared tunnel --url http://localhost:8000
