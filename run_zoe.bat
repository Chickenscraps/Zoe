@echo off
TITLE Zoe V3 (Clawdbot)

echo ============================================
echo   Zoe V3 (Gemini 2.0 / Supabase / ChatOps)
echo ============================================
echo.

echo [START] Launching Zoe...
python clawdbot.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Zoe crashed with error code %ERRORLEVEL%.
    pause
)
pause
