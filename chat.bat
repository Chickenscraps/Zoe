@echo off
REM Quick Chat Helper for OpenClaw Local Agent
REM Usage: chat "Your message here"

if "%~1"=="" (
    echo Usage: chat "Your message here"
    exit /b 1
)

pnpm openclaw chat --url ws://localhost:18789/ws "%~1"
