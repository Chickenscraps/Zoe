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
    @{ Name = 'adb-mcp (AI agent control for Adobe apps)'; Url = 'https://github.com/mikechambers/adb-mcp' }
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
# 7. AI music/video/asset bookmarks (browser tabs)
# ============================================================
Write-Host "`n--- Opening AI creative services ---" -ForegroundColor Yellow
Write-Host "  These are freemium web services — sign up for free tiers:`n"

$aiServices = @(
    @{ Name = 'Pika (AI video, 30 free credits/day)';  Url = 'https://pika.art' }
    @{ Name = 'Runway (AI video, 125 free credits)';   Url = 'https://runwayml.com' }
    @{ Name = 'Suno (AI music generation)';             Url = 'https://suno.com' }
    @{ Name = 'Udio (AI music + stem isolation)';       Url = 'https://udio.com' }
    @{ Name = 'AIVA (cinematic AI scoring)';            Url = 'https://aiva.ai' }
    @{ Name = 'ElevenLabs (AI voice + music)';          Url = 'https://elevenlabs.io' }
    @{ Name = 'Coolors (color palette generator)';      Url = 'https://coolors.co' }
    @{ Name = 'Adobe Color (palette + CC Libraries)';   Url = 'https://color.adobe.com' }
    @{ Name = 'Poly Haven (free HDRIs/textures/3D)';   Url = 'https://polyhaven.com' }
    @{ Name = 'Pexels (free stock photos/video)';      Url = 'https://www.pexels.com' }
    @{ Name = 'Pixabay (free stock assets)';            Url = 'https://pixabay.com' }
    @{ Name = 'Freesound (free sound effects)';         Url = 'https://freesound.org' }
    @{ Name = 'Mixkit (free video/music/SFX)';          Url = 'https://mixkit.co' }
    @{ Name = 'Google Fonts';                            Url = 'https://fonts.google.com' }
)

foreach ($svc in $aiServices) {
    Write-Host "    $($svc.Name)"
    Start-Process $svc.Url
    Start-Sleep -Milliseconds 400
}

# ============================================================
# 8. ComfyUI essential custom nodes (instructions)
# ============================================================
Write-Host "`n--- ComfyUI recommended custom nodes ---" -ForegroundColor Yellow

$comfyMsg = @"

  After ComfyUI is installed, open it and use ComfyUI Manager to install:

    - ComfyUI Manager        (node management, essential)
    - WAS Node Suite          (hundreds of utility nodes)
    - Impact Pack             (face detailing, segmentation)
    - AnimateDiff             (video/animation generation)
    - Advanced ControlNet     (pose and composition control)
    - ComfyUI Essentials      (missing core functionality)
    - ComfyUI-SAM3            (Segment Anything Model 3)
    - LayerForge              (Photoshop-like canvas in ComfyUI)
    - ComfyUI-VideoUpscale    (memory-efficient video upscaling)

  Recommended models to download via ComfyUI Manager:
    - Flux 2 (best overall quality for local generation)
    - Stable Diffusion XL (largest LoRA/ControlNet ecosystem)
    - Wan 2.2 1.3B (video generation, only needs ~8GB VRAM)

"@
Write-Host $comfyMsg -ForegroundColor White

# ============================================================
# Summary
# ============================================================
Write-Host "=== Creative Tools Setup Complete ===" -ForegroundColor Green

if ($failed.Count -gt 0) {
    Write-Host "`nFailed to install via winget (install manually):" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}

$nextSteps = @"

  Next steps:
  1. Install Adobe apps from Creative Cloud:
       Photoshop, After Effects, Illustrator, Media Encoder
  2. Download AE/PS plugins from the pages that opened
  3. Install ZXP/UXP Installer first, then use it to install .zxp/.ccx plugins
  4. Sign up for free tiers on AI services (Pika, Runway, Suno, etc.)
  5. Launch ComfyUI and install recommended custom nodes via Manager
  6. Download DaVinci Resolve from the page that opened
  7. Set up adb-mcp for AI agent control of Photoshop/AE:
       git clone https://github.com/mikechambers/adb-mcp
       Follow README for Python + Node.js + UXP plugin setup

"@
Write-Host $nextSteps -ForegroundColor White
