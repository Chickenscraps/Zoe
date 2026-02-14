# tune-windows-dev.ps1
# Configures Windows as a development machine: power plan, Explorer tweaks,
# developer mode, WSL, useful Windows features, and terminal defaults.
# Run elevated: powershell -ExecutionPolicy Bypass -File scripts/tune-windows-dev.ps1

#Requires -RunAsAdministrator
#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

Write-Host "`n=== Windows Dev Tuning ===" -ForegroundColor Cyan

# ============================================================
# 1. Power plan — High Performance
# ============================================================
Write-Host "`n--- Setting High Performance power plan ---" -ForegroundColor Yellow
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
# Prevent sleep on AC power
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 30
# Disable USB selective suspend (avoids dev device disconnects)
powercfg /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /setactive SCHEME_CURRENT
Write-Host "  Power plan set to High Performance, sleep disabled on AC." -ForegroundColor Green

# ============================================================
# 2. Explorer — show extensions, hidden files, full path
# ============================================================
Write-Host "`n--- Configuring Explorer for development ---" -ForegroundColor Yellow

$explorerKey = "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"

# Show file extensions
reg add $explorerKey /v HideFileExt /t REG_DWORD /d 0 /f | Out-Null
# Show hidden files
reg add $explorerKey /v Hidden /t REG_DWORD /d 1 /f | Out-Null
# Show protected OS files (optional, uncomment if you want)
# reg add $explorerKey /v ShowSuperHidden /t REG_DWORD /d 1 /f | Out-Null
# Show full path in title bar
reg add $explorerKey /v FullPath /t REG_DWORD /d 1 /f | Out-Null
# Launch Explorer to "This PC" instead of Quick Access
reg add $explorerKey /v LaunchTo /t REG_DWORD /d 1 /f | Out-Null
# Disable recent files in Quick Access
reg add $explorerKey /v ShowRecent /t REG_DWORD /d 0 /f | Out-Null
# Show checkboxes for file selection
reg add $explorerKey /v AutoCheckSelect /t REG_DWORD /d 0 /f | Out-Null
# Expand navigation pane to current folder
reg add $explorerKey /v NavPaneExpandToCurrentFolder /t REG_DWORD /d 1 /f | Out-Null

Write-Host "  File extensions visible, hidden files shown, full path in title bar." -ForegroundColor Green

# ============================================================
# 3. Enable Developer Mode
# ============================================================
Write-Host "`n--- Enabling Developer Mode ---" -ForegroundColor Yellow
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" /v AllowDevelopmentWithoutDevLicense /t REG_DWORD /d 1 /f | Out-Null
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" /v AllowAllTrustedApps /t REG_DWORD /d 1 /f | Out-Null
Write-Host "  Developer Mode enabled." -ForegroundColor Green

# ============================================================
# 4. Enable useful Windows features
# ============================================================
Write-Host "`n--- Enabling Windows features ---" -ForegroundColor Yellow

$features = @(
    'Microsoft-Windows-Subsystem-Linux'
    'VirtualMachinePlatform'
    'Microsoft-Hyper-V-All'
    'Containers'
)

foreach ($feat in $features) {
    $state = Get-WindowsOptionalFeature -Online -FeatureName $feat -ErrorAction SilentlyContinue
    if ($state -and $state.State -ne 'Enabled') {
        Write-Host "  Enabling: $feat"
        Enable-WindowsOptionalFeature -Online -FeatureName $feat -NoRestart -ErrorAction SilentlyContinue | Out-Null
    } elseif ($state) {
        Write-Host "  Already enabled: $feat" -ForegroundColor DarkGray
    } else {
        Write-Host "  Not available: $feat" -ForegroundColor DarkGray
    }
}

# Install WSL2 default distro
Write-Host "`n  Installing WSL2 (Ubuntu default) ..."
wsl --install --no-launch 2>$null
wsl --set-default-version 2 2>$null

Write-Host "  WSL2, Hyper-V, and Containers enabled." -ForegroundColor Green

# ============================================================
# 5. Taskbar and UI tweaks
# ============================================================
Write-Host "`n--- Cleaning up taskbar ---" -ForegroundColor Yellow

$taskbarKey = "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
# Hide Task View button
reg add $taskbarKey /v ShowTaskViewButton /t REG_DWORD /d 0 /f | Out-Null
# Hide Widgets
reg add $taskbarKey /v TaskbarDa /t REG_DWORD /d 0 /f | Out-Null
# Hide Chat icon
reg add $taskbarKey /v TaskbarMn /t REG_DWORD /d 0 /f | Out-Null
# Left-align taskbar (uncomment for classic feel)
# reg add $taskbarKey /v TaskbarAl /t REG_DWORD /d 0 /f | Out-Null

# Hide Search box (show icon only)
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Search" /v SearchboxTaskbarMode /t REG_DWORD /d 1 /f | Out-Null

# Dark mode
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v AppsUseLightTheme /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v SystemUsesLightTheme /t REG_DWORD /d 0 /f | Out-Null

Write-Host "  Taskbar cleaned, dark mode enabled." -ForegroundColor Green

# ============================================================
# 6. Git global config defaults for dev
# ============================================================
Write-Host "`n--- Setting Git defaults ---" -ForegroundColor Yellow

$gitInstalled = Get-Command git -ErrorAction SilentlyContinue
if ($gitInstalled) {
    git config --global core.autocrlf input
    git config --global core.longpaths true
    git config --global init.defaultBranch main
    git config --global pull.rebase true
    git config --global fetch.prune true
    git config --global diff.algorithm histogram
    git config --global rerere.enabled true
    Write-Host "  Git configured (autocrlf=input, longpaths, rebase pull, histogram diff)." -ForegroundColor Green
} else {
    Write-Host "  Git not found — install it first, then re-run." -ForegroundColor DarkGray
}

# ============================================================
# 7. Set env vars for development
# ============================================================
Write-Host "`n--- Setting development environment variables ---" -ForegroundColor Yellow

# Prefer UTF-8 console
[System.Environment]::SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8', 'User')
[System.Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User')
# Node options
[System.Environment]::SetEnvironmentVariable('NODE_OPTIONS', '--max-old-space-size=8192', 'User')

Write-Host "  UTF-8 and Node memory env vars set." -ForegroundColor Green

# ============================================================
# 8. Privacy: disable Copilot / Recall / AI features if unwanted
# ============================================================
Write-Host "`n--- Disabling Windows Copilot and Recall ---" -ForegroundColor Yellow

# Disable Windows Copilot
reg add "HKCU\Software\Policies\Microsoft\Windows\WindowsCopilot" /v TurnOffWindowsCopilot /t REG_DWORD /d 1 /f | Out-Null
# Disable Recall
reg add "HKCU\Software\Policies\Microsoft\Windows\WindowsAI" /v DisableAIDataAnalysis /t REG_DWORD /d 1 /f | Out-Null

Write-Host "  Windows Copilot and Recall disabled." -ForegroundColor Green

# ============================================================
# 9. Performance: disable animations, transparency
# ============================================================
Write-Host "`n--- Tuning visual performance ---" -ForegroundColor Yellow

# Reduce animations
reg add "HKCU\Control Panel\Desktop" /v MenuShowDelay /t REG_SZ /d 0 /f | Out-Null
reg add "HKCU\Control Panel\Desktop\WindowMetrics" /v MinAnimate /t REG_SZ /d 0 /f | Out-Null
# Disable transparency
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v EnableTransparency /t REG_DWORD /d 0 /f | Out-Null

Write-Host "  Animations reduced, transparency disabled." -ForegroundColor Green

# ============================================================
Write-Host "`n=== Dev Tuning Complete ===" -ForegroundColor Green
Write-Host "Restart your computer (or at least Explorer) for all changes to take effect."
Write-Host "After reboot, run 'wsl' to finish Ubuntu setup.`n"
