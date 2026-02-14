# setup-creative-tools.ps1
# Installs creative apps, AE/PS plugins, AI art tools, and companion utilities.
# Run as: powershell -ExecutionPolicy Bypass -File scripts/setup-creative-tools.ps1
#
# Adobe CC apps (Photoshop, After Effects, Illustrator, Media Encoder) must be
# installed from the Creative Cloud desktop app — this script handles everything else.

#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

Write-Host "`n=== Creative Tools Setup ===" -ForegroundColor Cyan

# ============================================================
# 1. Core creative apps via winget
# ============================================================
Write-Host "`n--- Installing creative desktop apps ---" -ForegroundColor Yellow

$creativePackages = @(
    @{ Id = 'BlenderFoundation.Blender';       Desc = 'Blender (3D modeling/animation/rendering)' }
    @{ Id = 'OBSProject.OBSStudio';            Desc = 'OBS Studio (screen recording/streaming)' }
    @{ Id = 'HandBrake.HandBrake';             Desc = 'HandBrake (video transcoding)' }
    @{ Id = 'Gyan.FFmpeg';                     Desc = 'FFmpeg (CLI video/audio processing)' }
    @{ Id = 'VideoLAN.VLC';                    Desc = 'VLC (universal media player)' }
    @{ Id = 'Inkscape.Inkscape';               Desc = 'Inkscape (vector graphics editor)' }
    @{ Id = 'KDE.Kdenlive';                    Desc = 'Kdenlive (video editor)' }
    @{ Id = 'Audacity.Audacity';               Desc = 'Audacity (audio editor)' }
    @{ Id = 'DuongDieuPhap.ImageGlass';        Desc = 'ImageGlass (fast image viewer)' }
)

$failed = @()
foreach ($pkg in $creativePackages) {
    Write-Host "`n  Installing $($pkg.Desc) ($($pkg.Id)) ..."
    winget install -e --id $pkg.Id --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        $failed += $pkg.Id
    }
}

# ============================================================
# 2. AI image/video tools via winget
# ============================================================
Write-Host "`n--- Installing AI creative tools ---" -ForegroundColor Yellow

$aiCreativePackages = @(
    @{ Id = 'Upscayl.Upscayl';                Desc = 'Upscayl (AI image upscaler)' }
    @{ Id = 'comfyanonymous.ComfyUI';          Desc = 'ComfyUI Desktop (AI image/video generation)' }
)

foreach ($pkg in $aiCreativePackages) {
    Write-Host "`n  Installing $($pkg.Desc) ($($pkg.Id)) ..."
    winget install -e --id $pkg.Id --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        # Some AI tools may not be on winget yet — track for manual install
        $failed += $pkg.Id
    }
}

# ============================================================
# 3. DaVinci Resolve (not on winget — download page)
# ============================================================
Write-Host "`n--- DaVinci Resolve ---" -ForegroundColor Yellow

$resolveInstalled = Get-Command 'Resolve' -ErrorAction SilentlyContinue
$resolvePath = "${env:ProgramFiles}\Blackmagic Design\DaVinci Resolve\Resolve.exe"
if (Test-Path $resolvePath) {
    Write-Host "  DaVinci Resolve already installed." -ForegroundColor DarkGray
} else {
    Write-Host "  DaVinci Resolve requires manual download (free registration)."
    Write-Host "  Opening download page ..."
    Start-Process 'https://www.blackmagicdesign.com/products/davinciresolve'
}

# ============================================================
# 4. Font management
# ============================================================
Write-Host "`n--- Installing font tools ---" -ForegroundColor Yellow

# FontBase (not on winget — direct download)
$fontbasePath = "${env:LOCALAPPDATA}\Programs\FontBase\FontBase.exe"
if (Test-Path $fontbasePath) {
    Write-Host "  FontBase already installed." -ForegroundColor DarkGray
} else {
    Write-Host "  FontBase requires manual download."
    Write-Host "  Opening download page ..."
    Start-Process 'https://fontba.se/'
}

# Google Fonts directory
Write-Host "  Tip: browse fonts at https://fonts.google.com" -ForegroundColor DarkGray

# ============================================================
# 5. After Effects free plugins (download pages)
# ============================================================
Write-Host "`n--- After Effects free plugins ---" -ForegroundColor Yellow
Write-Host "  Opening download pages for essential free AE plugins ...`n"

$aePlugins = @(
    @{ Name = 'FX Console (Video Copilot)';    Url = 'https://www.videocopilot.net/blog/2016/10/new-workflow-plug-in-fx-console/' }
    @{ Name = 'Duik Ange (character rigging)';  Url = 'https://rxlaboratory.org/tools/duik-ange/' }
    @{ Name = 'Bodymovin / Lottie (web export)'; Url = 'https://aescripts.com/bodymovin/' }
    @{ Name = 'Saber (light/energy effects)';  Url = 'https://www.videocopilot.net/tutorials/saber_plug-in/' }
    @{ Name = 'ORB (3D spheres/planets)';      Url = 'https://www.videocopilot.net/orb/' }
    @{ Name = 'EaseCopy (easing curves)';      Url = 'https://aescripts.com/easecopy/' }
    @{ Name = 'Motion Tools 2 (animation utils)'; Url = 'https://www.motion.design/motion-tools' }
    @{ Name = 'ReDefine (matte refinement)';   Url = 'https://aescripts.com/redefine/' }
    @{ Name = 'aescripts free collection';     Url = 'https://aescripts.com/free/' }
)

foreach ($plugin in $aePlugins) {
    Write-Host "    $($plugin.Name)"
    Start-Process $plugin.Url
    Start-Sleep -Milliseconds 600
}

# ============================================================
# 6. Photoshop free plugins & AI bridges (download pages)
# ============================================================
Write-Host "`n--- Photoshop free plugins & AI bridges ---" -ForegroundColor Yellow
Write-Host "  Opening download pages for PS plugins ...`n"

$psPlugins = @(
    @{ Name = 'Auto-Photoshop-SD Plugin (Stable Diffusion in PS)'; Url = 'https://github.com/AbdullahAlfaraj/Auto-Photoshop-StableDiffusion-Plugin' }
    @{ Name = 'ComfyUI-Photoshop bridge';      Url = 'https://github.com/NimaNzrii/comfyui-photoshop' }
    @{ Name = 'ZXP/UXP Installer (plugin installer)'; Url = 'https://aescripts.com/learn/post/zxp-installer/' }
    @{ Name = 'Pexels stock photos plugin';    Url = 'https://exchange.adobe.com/' }
    @{ Name = 'Alpaca AI (search Adobe Exchange)'; Url = 'https://exchange.adobe.com/' }
)

foreach ($plugin in $psPlugins) {
    Write-Host "    $($plugin.Name)"
    Start-Process $plugin.Url
    Start-Sleep -Milliseconds 600
}

# ============================================================
# 7. ComfyUI essential custom nodes (instructions)
# ============================================================
Write-Host "`n--- ComfyUI recommended custom nodes ---" -ForegroundColor Yellow

Write-Host ""
Write-Host "  After ComfyUI is installed, open it and use ComfyUI Manager to install:" -ForegroundColor White
Write-Host ""
Write-Host "    * ComfyUI Manager        (node management, essential)" -ForegroundColor White
Write-Host "    * WAS Node Suite          (hundreds of utility nodes)" -ForegroundColor White
Write-Host "    * Impact Pack             (face detailing, segmentation)" -ForegroundColor White
Write-Host "    * AnimateDiff             (video/animation generation)" -ForegroundColor White
Write-Host "    * Advanced ControlNet     (pose and composition control)" -ForegroundColor White
Write-Host "    * ComfyUI Essentials      (missing core functionality)" -ForegroundColor White
Write-Host "    * ComfyUI-SAM3            (Segment Anything Model 3)" -ForegroundColor White
Write-Host "    * LayerForge              (Photoshop-like canvas in ComfyUI)" -ForegroundColor White
Write-Host "    * ComfyUI-VideoUpscale    (memory-efficient video upscaling)" -ForegroundColor White
Write-Host ""
Write-Host "  Recommended models to download via ComfyUI Manager:" -ForegroundColor White
Write-Host "    * Flux 2 (best overall quality for local generation)" -ForegroundColor White
Write-Host "    * Stable Diffusion XL (largest LoRA/ControlNet ecosystem)" -ForegroundColor White
Write-Host "    * Wan 2.2 1.3B (video generation, only needs ~8GB VRAM)" -ForegroundColor White
Write-Host ""

# ============================================================
# 8. adb-mcp — AI agent control for Photoshop, After Effects,
#    Illustrator, Premiere, and InDesign
# ============================================================
Write-Host "`n--- Setting up adb-mcp (AI agent <-> Adobe apps bridge) ---" -ForegroundColor Yellow

$adbMcpDir = Join-Path $env:USERPROFILE 'adb-mcp'

# Install uv (Python package runner) if missing
if (-not (Get-Command 'uv' -ErrorAction SilentlyContinue)) {
    Write-Host "  Installing uv (Python package runner) ..."
    winget install -e --id astral-sh.uv --source winget --accept-package-agreements --accept-source-agreements
    # Refresh PATH so uv is available in this session
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('Path', 'User')
}

# Clone the repo
if (Test-Path (Join-Path $adbMcpDir '.git')) {
    Write-Host "  adb-mcp already cloned at $adbMcpDir — pulling latest ..." -ForegroundColor DarkGray
    git -C $adbMcpDir pull --rebase origin main 2>$null
} else {
    Write-Host "  Cloning adb-mcp ..."
    git clone https://github.com/mikechambers/adb-mcp $adbMcpDir
}

if (Test-Path $adbMcpDir) {
    # Install MCP servers for Photoshop and After Effects
    Push-Location $adbMcpDir

    $mcpDeps = '--with', 'fonttools', '--with', 'python-socketio', '--with', 'mcp',
               '--with', 'requests', '--with', 'websocket-client'

    Write-Host "  Installing Photoshop MCP server ..."
    & uv run mcp install @mcpDeps --with numpy ps-mcp.py 2>$null

    Write-Host "  Installing After Effects MCP server ..."
    & uv run mcp install @mcpDeps --with numpy ae-mcp.py 2>$null

    Write-Host "  Installing Illustrator MCP server ..."
    & uv run mcp install @mcpDeps --with numpy ai-mcp.py 2>$null

    # Install proxy server dependencies
    $proxyDir = Join-Path $adbMcpDir 'adb-proxy-socket'
    if (Test-Path $proxyDir) {
        Write-Host "  Installing proxy server dependencies ..."
        Push-Location $proxyDir
        npm install --silent 2>$null
        Pop-Location
    }

    Pop-Location

    # Set up CEP extension junctions for After Effects + Illustrator
    $cepBase = Join-Path $env:APPDATA 'Adobe\CEP\extensions'
    if (-not (Test-Path $cepBase)) {
        New-Item -ItemType Directory -Path $cepBase -Force | Out-Null
    }

    $cepPlugins = @(
        @{ Name = 'com.mikechambers.ae'; Desc = 'After Effects' }
        @{ Name = 'com.mikechambers.ai'; Desc = 'Illustrator' }
    )

    foreach ($cep in $cepPlugins) {
        $src  = Join-Path $adbMcpDir "cep\$($cep.Name)"
        $dest = Join-Path $cepBase $cep.Name
        if ((Test-Path $src) -and -not (Test-Path $dest)) {
            Write-Host "  Creating CEP junction for $($cep.Desc) ..."
            cmd /c mklink /D "`"$dest`"" "`"$src`"" 2>$null | Out-Null
        } elseif (Test-Path $dest) {
            Write-Host "  CEP junction for $($cep.Desc) already exists." -ForegroundColor DarkGray
        }
    }

    Write-Host ""
    Write-Host "  adb-mcp installed at: $adbMcpDir" -ForegroundColor White
    Write-Host ""
    Write-Host "  To use adb-mcp:" -ForegroundColor White
    Write-Host "    1. Start the proxy:  node $proxyDir\proxy.js" -ForegroundColor White
    Write-Host "    2. Open Adobe UXP Developer Tool (install from Creative Cloud)" -ForegroundColor White
    Write-Host "    3. File > Add Plugin > select the manifest.json for your app:" -ForegroundColor White
    Write-Host "         Photoshop:  $adbMcpDir\uxp\ps\manifest.json" -ForegroundColor White
    Write-Host "         Premiere:   $adbMcpDir\uxp\pr\manifest.json" -ForegroundColor White
    Write-Host "         InDesign:   $adbMcpDir\uxp\id\manifest.json" -ForegroundColor White
    Write-Host "    4. Click Load, then open the plugin panel in the Adobe app and hit Connect" -ForegroundColor White
    Write-Host "    5. AE + Illustrator use CEP (junctions already created above)" -ForegroundColor White
    Write-Host "       Enable: Edit > Preferences > Scripting > Allow Scripts to Write Files" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "  Failed to clone adb-mcp — install manually from:" -ForegroundColor Red
    Write-Host "    https://github.com/mikechambers/adb-mcp" -ForegroundColor Red
}

# ============================================================
# Summary
# ============================================================
Write-Host "=== Creative Tools Setup Complete ===" -ForegroundColor Green

if ($failed.Count -gt 0) {
    Write-Host "`nFailed to install via winget (install manually):" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}

Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. Install Adobe apps from Creative Cloud:" -ForegroundColor White
Write-Host "       Photoshop, After Effects, Illustrator, Media Encoder" -ForegroundColor White
Write-Host "  2. Download AE/PS plugins from the pages that opened" -ForegroundColor White
Write-Host "  3. Install ZXP/UXP Installer first, then use it to install .zxp/.ccx plugins" -ForegroundColor White
Write-Host "  4. Launch ComfyUI and install recommended custom nodes via Manager" -ForegroundColor White
Write-Host "  5. Download DaVinci Resolve from the page that opened" -ForegroundColor White
Write-Host "  6. Start the adb-mcp proxy and load UXP plugins (see instructions above)" -ForegroundColor White
Write-Host ""
