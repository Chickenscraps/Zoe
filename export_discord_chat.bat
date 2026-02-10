@echo off
REM Discord Chat Exporter Helper Script
REM Exports the group DM chat to JSON format

echo ========================================
echo Discord Chat Exporter
echo ========================================
echo.

REM Check if DiscordChatExporter exists
if not exist "DiscordChatExporter\DiscordChatExporter.Cli.exe" (
    echo ERROR: DiscordChatExporter not found!
    echo Please run: python setup_chat_exporter.py
    pause
    exit /b 1
)

echo This script will export your Discord group DM.
echo.
echo You'll need:
echo   1. Your Discord token
echo   2. Channel ID: 799704432929406998
echo.
echo ========================================
echo How to get your Discord token:
echo ========================================
echo Method 1 (Easiest):
echo   1. Open Discord in browser (discord.com)
echo   2. Press F12 for Developer Tools
echo   3. Go to Network tab
echo   4. Press Ctrl+R to reload
echo   5. Type 'api' in filter
echo   6. Click any discord.com/api request
echo   7. Find 'authorization:' in Request Headers
echo   8. Copy the value - that's your token!
echo.
echo Method 2:
echo   1. F12 -^> Application tab
echo   2. Local Storage -^> discord.com
echo   3. Find key with 'token'
echo   4. Copy the value
echo.
echo WARNING: Keep your token private!
echo ========================================
echo.

set /p TOKEN="Enter your Discord token: "

if "%TOKEN%"=="" (
    echo ERROR: Token cannot be empty!
    pause
    exit /b 1
)

echo.
echo Exporting chat...
echo Channel: 799704432929406998
echo Output: group_dm_export.json
echo.

DiscordChatExporter\DiscordChatExporter.Cli.exe export ^
    -t "%TOKEN%" ^
    -c 799704432929406998 ^
    -f Json ^
    -o group_dm_export.json

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! Chat exported to group_dm_export.json
    echo ========================================
    echo.
    echo Next steps:
    echo   1. Run: python parse_discord_export.py group_dm_export.json
    echo   2. Run: python extract_personas.py
    echo.
) else (
    echo.
    echo ERROR: Export failed!
    echo Check that your token is correct and you have access to the channel.
    echo.
)

pause
