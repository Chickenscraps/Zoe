# setup-windows-tools.ps1
# Installs development tools via winget and opens Chrome extensions for manual install.
# Run as: powershell -ExecutionPolicy Bypass -File scripts/setup-windows-tools.ps1

#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

# --- winget packages ---
$wingetPackages = @(
    'Microsoft.WindowsTerminal'
    'Docker.DockerDesktop'
    'Postman.Postman'
    'WinSCP.WinSCP'
    'PuTTY.PuTTY'
    'voidtools.Everything'
    'File-New-Project.EarTrumpet'
    '7zip.7zip'
    'ShareX.ShareX'
    'Notepad++.Notepad++'
    'Discord.Discord'
    'SlackTechnologies.Slack'
    'VideoLAN.VLC'
    'OBSProject.OBSStudio'
    'Spotify.Spotify'
    'Adobe.CreativeCloud'
)

# --- Chrome extensions (must be installed manually via browser) ---
$chromeExtensions = @(
    @{ Name = 'uBlock Origin';           Url = 'https://chromewebstore.google.com/detail/ublock-origin/cjpalhdlnbpafiamejdnhcphjbkeiagm' }
    @{ Name = 'Vimium';                  Url = 'https://chromewebstore.google.com/detail/vimium/dbepggeogbaibhgnhhndojpepiihcmeb' }
    @{ Name = 'Dark Reader';             Url = 'https://chromewebstore.google.com/detail/dark-reader/eimadpbcbfnmbkopoojfekhnkhdbieeh' }
    @{ Name = 'OneTab';                  Url = 'https://chromewebstore.google.com/detail/onetab/chphlpgkkbolifaimnlloiipkdnihall' }
    @{ Name = 'Refined GitHub';          Url = 'https://chromewebstore.google.com/detail/refined-github/hlepfoohegkhhmjieoechaddaejaokhf' }
    @{ Name = 'JSON Viewer';             Url = 'https://chromewebstore.google.com/detail/json-viewer/gbmdgpbipfallnflgajpaliibnhdgobh' }
    @{ Name = 'Wappalyzer';              Url = 'https://chromewebstore.google.com/detail/wappalyzer/gppongmhjkpfnbhagpmjfkannfbllamg' }
    @{ Name = 'React Developer Tools';   Url = 'https://chromewebstore.google.com/detail/react-developer-tools/fmkadmapgofadopljbjfkapdkoienihi' }
    @{ Name = 'Bitwarden';               Url = 'https://chromewebstore.google.com/detail/bitwarden/nngceckbapebfimnlniiiahkandclblb' }
    @{ Name = 'Privacy Badger';          Url = 'https://chromewebstore.google.com/detail/privacy-badger/pkehgijcmpdhfbdbbnkijodmhjibjlgi' }
)

Write-Host "`n=== Windows Tools Setup ===" -ForegroundColor Cyan

# ---- Install winget packages ----
Write-Host "`n--- Installing winget packages ---" -ForegroundColor Yellow

$failed = @()
foreach ($pkg in $wingetPackages) {
    Write-Host "`nInstalling $pkg ..." -ForegroundColor White
    winget install -e --id $pkg --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        $failed += $pkg
    }
}

# ---- Chrome extensions ----
Write-Host "`n--- Opening Chrome extensions ---" -ForegroundColor Yellow
Write-Host "Each extension page will open in your browser. Click 'Add to Chrome' to install.`n"

foreach ($ext in $chromeExtensions) {
    Write-Host "  Opening $($ext.Name) ..."
    Start-Process $ext.Url
    Start-Sleep -Milliseconds 800
}

# ---- Summary ----
Write-Host "`n=== Setup Complete ===" -ForegroundColor Green

if ($failed.Count -gt 0) {
    Write-Host "`nThe following packages failed to install:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "Re-run the script or install them manually with: winget install -e --id <ID> --source winget"
}

Write-Host "`nChrome extensions were opened in your browser -- install them manually if not already added.`n"
