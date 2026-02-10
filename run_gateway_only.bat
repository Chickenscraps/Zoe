@echo off
TITLE Clawdbot Discord Gateway Debug

echo ============================================
echo   Clawdbot Gateway Debug
echo ============================================
echo.

REM Set Python Path
set "PYTHONPATH=%CD%;%CD%\AGENT PERSONA SKILL;%PYTHONPATH%"

echo [START] Launching Discord Gateway...
python discord_gateway.py

echo.
echo Gateway process ended.
pause
