# debloat-hp-windows.ps1
# Removes HP bloatware, Windows junk apps, and disables telemetry/ads.
# Run elevated: powershell -ExecutionPolicy Bypass -File scripts/debloat-hp-windows.ps1

#Requires -RunAsAdministrator
#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

Write-Host "`n=== HP & Windows Debloat ===" -ForegroundColor Cyan
Write-Host "This script removes bloatware and disables telemetry. Requires admin.`n"

# ============================================================
# 1. Remove HP bloatware (Appx packages)
# ============================================================
Write-Host "--- Removing HP bloatware (Appx) ---" -ForegroundColor Yellow

$hpAppxPatterns = @(
    '*HPAudioControl*'
    '*HPSystemInformation*'
    '*HPQuickDrop*'
    '*HPPowerManager*'
    '*HPPrivacySettings*'
    '*HPProgrammableKey*'
    '*HPAccessoryCenter*'
    '*HPPCHardwareDiagnosticsWindows*'
    '*HPSupportAssistant*'
    '*HPDesktopSupportUtilities*'
    '*HPQuickTouch*'
    '*HPSureShieldAI*'
    '*HPWorkWell*'
    '*myHP*'
    '*HPSmartExperiences*'
    '*AD2F1837*'  # HP common app ID prefix
)

foreach ($pattern in $hpAppxPatterns) {
    $apps = Get-AppxPackage -AllUsers -Name $pattern 2>$null
    foreach ($app in $apps) {
        Write-Host "  Removing: $($app.Name)" -ForegroundColor Red
        $app | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue
        Get-AppxProvisionedPackage -Online | Where-Object DisplayName -Like $pattern |
            Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue
    }
}

# Remove HP Win32 programs via winget
Write-Host "`n--- Removing HP Win32 programs ---" -ForegroundColor Yellow

$hpWingetIds = @(
    'HP.HPSupportAssistant'
    'HP.HPSmart'
    'HP.HPDocumentation'
    'HP.HPAudioCenter'
    'HP.HPSecurityUpdateService'
    'HP.HPPrivacySettings'
    'HP.HPSADIS'
    'HP.HPSureRunModule'
    'HP.HPSystemDefaultSettings'
    'HP.HPWolfSecurity'
    'HP.HPWolfSecurityConsole'
)

foreach ($id in $hpWingetIds) {
    Write-Host "  Uninstalling $id ..."
    winget uninstall --id $id --silent --accept-source-agreements 2>$null
}

# ============================================================
# 2. Remove Windows bloatware
# ============================================================
Write-Host "`n--- Removing Windows bloatware ---" -ForegroundColor Yellow

$windowsBloat = @(
    'Microsoft.BingNews'
    'Microsoft.BingWeather'
    'Microsoft.BingFinance'
    'Microsoft.BingSports'
    'Microsoft.GamingApp'
    'Microsoft.GetHelp'
    'Microsoft.Getstarted'
    'Microsoft.MicrosoftSolitaireCollection'
    'Microsoft.MicrosoftOfficeHub'
    'Microsoft.People'
    'Microsoft.PowerAutomateDesktop'
    'Microsoft.Todos'
    'Microsoft.WindowsFeedbackHub'
    'Microsoft.WindowsMaps'
    'Microsoft.Xbox.TCUI'
    'Microsoft.XboxGameOverlay'
    'Microsoft.XboxGamingOverlay'
    'Microsoft.XboxIdentityProvider'
    'Microsoft.XboxSpeechToTextOverlay'
    'Microsoft.YourPhone'
    'Microsoft.ZuneMusic'
    'Microsoft.ZuneVideo'
    'MicrosoftTeams'
    'Clipchamp.Clipchamp'
    'Microsoft.549981C3F5F10'  # Cortana
    'Disney.37853FC22B2CE'     # Disney+
    'SpotifyAB.SpotifyMusic'   # Pre-installed Spotify stub (you install the real one separately)
    'king.com.CandyCrushSaga'
    'king.com.CandyCrushSodaSaga'
    'BytedancePte.Ltd.TikTok'
    'FACEBOOK.FACEBOOK'
    'Facebook.Instagram'
)

foreach ($bloat in $windowsBloat) {
    $apps = Get-AppxPackage -AllUsers -Name $bloat 2>$null
    if ($apps) {
        Write-Host "  Removing: $bloat" -ForegroundColor Red
        $apps | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue
        Get-AppxProvisionedPackage -Online | Where-Object DisplayName -eq $bloat |
            Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue
    }
}

# ============================================================
# 3. Disable telemetry, ads, and tracking
# ============================================================
Write-Host "`n--- Disabling telemetry, ads, and tracking ---" -ForegroundColor Yellow

# Disable advertising ID
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo" /v Enabled /t REG_DWORD /d 0 /f | Out-Null

# Disable Start menu suggestions / ads
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v SubscribedContent-338389Enabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v SubscribedContent-310093Enabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v SubscribedContent-338388Enabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v SubscribedContent-353698Enabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v SystemPaneSuggestionsEnabled /t REG_DWORD /d 0 /f | Out-Null

# Disable Bing search in Start menu
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Search" /v BingSearchEnabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Search" /v CortanaConsent /t REG_DWORD /d 0 /f | Out-Null

# Disable tips and tricks notifications
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v SoftLandingEnabled /t REG_DWORD /d 0 /f | Out-Null

# Disable lock screen tips/ads
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v RotatingLockScreenEnabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v RotatingLockScreenOverlayEnabled /t REG_DWORD /d 0 /f | Out-Null

# Disable pre-installed app suggestions
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v PreInstalledAppsEnabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v PreInstalledAppsEverEnabled /t REG_DWORD /d 0 /f | Out-Null
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" /v OemPreInstalledAppsEnabled /t REG_DWORD /d 0 /f | Out-Null

# Reduce diagnostic/telemetry data to minimum
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection" /v AllowTelemetry /t REG_DWORD /d 0 /f | Out-Null

# Disable activity history
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v EnableActivityFeed /t REG_DWORD /d 0 /f | Out-Null
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\System" /v PublishUserActivities /t REG_DWORD /d 0 /f | Out-Null

Write-Host "  Telemetry, ads, and tracking disabled." -ForegroundColor Green

# ============================================================
# 4. Disable unnecessary services
# ============================================================
Write-Host "`n--- Disabling unnecessary services ---" -ForegroundColor Yellow

$servicesToDisable = @(
    'DiagTrack'             # Connected User Experiences and Telemetry
    'dmwappushservice'      # WAP Push Message Routing
    'MapsBroker'            # Downloaded Maps Manager
    'RetailDemo'            # Retail Demo Service
)

foreach ($svc in $servicesToDisable) {
    $service = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if ($service) {
        Write-Host "  Disabling: $svc ($($service.DisplayName))"
        Stop-Service -Name $svc -Force -ErrorAction SilentlyContinue
        Set-Service -Name $svc -StartupType Disabled -ErrorAction SilentlyContinue
    }
}

# ============================================================
# 5. Remove HP scheduled tasks
# ============================================================
Write-Host "`n--- Removing HP scheduled tasks ---" -ForegroundColor Yellow

Get-ScheduledTask | Where-Object { $_.TaskName -match 'HP|Hewlett' } | ForEach-Object {
    Write-Host "  Disabling task: $($_.TaskName)"
    $_ | Disable-ScheduledTask -ErrorAction SilentlyContinue
}

Write-Host "`n=== Debloat Complete ===" -ForegroundColor Green
Write-Host "Restart your computer for all changes to take effect.`n"
