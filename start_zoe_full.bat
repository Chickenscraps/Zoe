@echo off
TITLE Zoe Full Stack Launcher
COLOR 0A

echo.
echo  =============================================
echo       ZOE FULL STACK - Bot + Dashboard
echo  =============================================
echo.
echo  [BOT]       Python Discord Bot (clawdbot.py)
echo  [TERMINAL]  Zoe Terminal Dashboard (React)
echo  [PIPELINE]  Crypto Structure Pipeline
echo  =============================================
echo.

REM ─── Set Python path to include project root ───
set "PYTHONPATH=%CD%;%PYTHONPATH%"

REM ─── Step 1: Pre-flight checks ───
echo [1/5] Running pre-flight checks...

REM Check Python is available
python --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   ERROR: Python not found in PATH.
    pause
    exit /b 1
)

REM Check config.yaml exists
if not exist "config.yaml" (
    echo   ERROR: config.yaml not found in %CD%
    pause
    exit /b 1
)

REM Check .env exists
if not exist ".env" (
    echo   WARNING: .env file not found. Bot may fail to start.
    echo   Continuing anyway...
)

echo   OK: Pre-flight checks passed.
echo.

REM ─── Step 2: Start Zoe Bot ───
echo [2/5] Starting Zoe Bot (Discord + Trading Engine + Crypto Pipeline)...
start "Zoe Bot" cmd /k "color 0E && title Zoe Bot (clawdbot.py) && python clawdbot.py"
echo   STARTED: Zoe Bot launching in separate window.
echo.

REM ─── Step 3: Wait for bot initialization ───
echo [3/5] Waiting for bot initialization (8 seconds)...
timeout /t 8 /nobreak >nul
echo   OK: Bot should be initialized.
echo.

REM ─── Step 4: Start Zoe Terminal Dashboard ───
echo [4/5] Starting Zoe Terminal Dashboard...
if exist "zoe-terminal\package.json" (
    start "Zoe Terminal" cmd /k "color 0B && title Zoe Terminal (Dashboard) && cd zoe-terminal && npm run dev"
    echo   STARTED: Dashboard launching in separate window.
) else (
    echo   SKIP: zoe-terminal/package.json not found. Dashboard not available.
)
echo.

REM ─── Step 5: Open dashboard in browser ───
echo [5/5] Opening dashboard in browser (5 second delay)...
timeout /t 5 /nobreak >nul
start http://localhost:5173
echo   DONE: Browser opened to http://localhost:5173
echo.

echo  =============================================
echo        ALL SYSTEMS LAUNCHED
echo  =============================================
echo.
echo  Bot:       Python process (yellow window)
echo  Dashboard: http://localhost:5173 (blue window)
echo.
echo  To stop: Close the individual command windows
echo           or press Ctrl+C in each.
echo.
echo  Config:    config.yaml
echo  Bounce:    Shadow mode (set bounce.enabled: true for live)
echo  =============================================
echo.
pause
