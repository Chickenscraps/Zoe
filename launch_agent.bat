@echo off
TITLE Clawdbot Launcher

echo ============================================
echo   Clawdbot V2 Launcher
echo ============================================
echo.

REM Set Python Path to include Skill Dir
set "PYTHONPATH=%CD%;%CD%\AGENT PERSONA SKILL;%PYTHONPATH%"

echo [START] Launching API Server (Port 8000)...
start "Clawdbot Server" cmd /k "cd AGENT PERSONA SKILL && python server.py"

timeout /t 5 >nul

echo [START] Launching Proactive Agent...
start "Clawdbot Proactive Agent" cmd /k "python proactive_agent.py"

echo [START] Launching Discord Gateway...
start "Clawdbot Discord Gateway" cmd /k "python discord_gateway.py"

echo.
echo [INFO] Systems launching in separate windows.
echo [INFO] Server API: http://localhost:8000
echo [INFO] Discord: Connecting...
echo.
pause
