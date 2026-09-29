@echo off
echo ==================================================
echo   HE THONG PHAT HIEN DRONE - KHOI DONG
echo ==================================================
echo.

REM Start web server in background
echo [1/2] Khoi dong web server...
start /B python app.py > server.log 2>&1
timeout /t 5 /nobreak > nul

REM Start cloudflared tunnel
echo [2/2] Tao link cong khai...
echo.
echo ===================================================
echo   Dang cho link cong khai...
echo   Mat khau truy cap: 1234
echo   Dung Ctrl+C de dung server
echo ===================================================
echo.
cloudflared tunnel --url http://localhost:8000 --no-tls-verify
