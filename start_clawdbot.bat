@echo off
REM Start Clawdbot AGI-Lite Discord Bot
REM Run Host Bridge, Health Check, and Discord Bot together

echo ============================================
echo   Clawdbot AGI-Lite Startup
echo ============================================
echo.

REM 1. Health Check
echo [STEP 1] Skipping Pre-Flight Health Checks (verify_clawd.py missing)...
REM python verify_clawd.py
REM if %ERRORLEVEL% NEQ 0 (
REM     echo.
REM     echo ❌ Pre-flight checks failed. Please fix the issues above before starting.
REM     pause
REM     exit /b %ERRORLEVEL%
REM )

REM 2. Host Bridge
echo.
echo [STEP 2] Checking Host Bridge Service...
tasklist /FI "WINDOWTITLE eq Host Bridge" 2>NUL | find /I "python.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    echo [OK] Host Bridge already running
) else (
    echo [START] Launching Host Bridge Service...
    start "Host Bridge" /MIN python host_bridge.py
    timeout /t 3 >nul
)

REM 3. Live Logs
echo.
echo [STEP 3] Opening Live Thought Log...
if exist "logs\live_transcript.jsonl" (
    start "Zoe's Brain (Live Logs)" powershell -NoExit -Command "Get-Content logs\live_transcript.jsonl -Wait -Tail 10"
)

REM 4. Discord Bot
echo.
echo [STEP 4] Launching Clawdbot Discord Bot...
python clawdbot.py

pause
