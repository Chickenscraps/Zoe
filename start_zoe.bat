@echo off
REM Zoe Daemon Wrapper Script
REM Automatically restarts on crash or hot-reload
REM Based on AGI Architecture Upgrade research §2.5

echo ========================================
echo    ZOE DAEMON - Auto-Restart Wrapper
echo ========================================

:loop
echo.
echo [%date% %time%] Starting Zoe...
python clawdbot.py
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE%==42 (
    echo [%date% %time%] Hot reload detected. Restarting immediately...
    goto loop
)

if %EXIT_CODE%==0 (
    echo [%date% %time%] Zoe exited cleanly. Goodbye.
    pause
    exit /b 0
)

echo [%date% %time%] Zoe crashed with code %EXIT_CODE%. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
