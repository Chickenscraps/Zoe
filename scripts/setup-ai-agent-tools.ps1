# setup-ai-agent-tools.ps1
# Installs AI coding assistants, agent frameworks, and related tools.
# Run as: powershell -ExecutionPolicy Bypass -File scripts/setup-ai-agent-tools.ps1

#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

Write-Host "`n=== AI & Agent Tools Setup ===" -ForegroundColor Cyan

# ============================================================
# 1. Install AI-powered editors and tools via winget
# ============================================================
Write-Host "`n--- Installing AI editors and tools ---" -ForegroundColor Yellow

$aiWingetPackages = @(
    @{ Id = 'Microsoft.VisualStudioCode';  Desc = 'VS Code (base editor for Copilot/extensions)' }
    @{ Id = 'Anysphere.Cursor';            Desc = 'Cursor (AI-native code editor)' }
    @{ Id = 'Windsurf.Windsurf';           Desc = 'Windsurf (Codeium AI editor)' }
    @{ Id = 'Anthropic.Claude';            Desc = 'Claude desktop app' }
    @{ Id = 'OpenAI.ChatGPT';             Desc = 'ChatGPT desktop app' }
    @{ Id = 'Ollama.Ollama';               Desc = 'Ollama (local LLM runner)' }
    @{ Id = 'LMStudio.LMStudio';           Desc = 'LM Studio (local model UI)' }
)

$failed = @()
foreach ($pkg in $aiWingetPackages) {
    Write-Host "`n  Installing $($pkg.Desc) ($($pkg.Id)) ..."
    winget install -e --id $pkg.Id --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        $failed += $pkg.Id
    }
}

# ============================================================
# 2. Install CLI AI tools via npm/pip
# ============================================================
Write-Host "`n--- Installing CLI AI tools ---" -ForegroundColor Yellow

# Claude Code (Anthropic CLI agent)
$npmInstalled = Get-Command npm -ErrorAction SilentlyContinue
if ($npmInstalled) {
    Write-Host "  Installing Claude Code (npm) ..."
    npm install -g @anthropic-ai/claude-code
} else {
    Write-Host "  npm not found — install Node.js first for Claude Code CLI" -ForegroundColor DarkGray
}

# Aider (AI pair programming CLI)
$pipInstalled = Get-Command pip -ErrorAction SilentlyContinue
if ($pipInstalled) {
    Write-Host "  Installing aider (pip) ..."
    pip install aider-chat
} else {
    Write-Host "  pip not found — install Python first for aider" -ForegroundColor DarkGray
}

# ============================================================
# 3. VS Code AI extensions
# ============================================================
Write-Host "`n--- Installing VS Code AI extensions ---" -ForegroundColor Yellow

$codeInstalled = Get-Command code -ErrorAction SilentlyContinue
if ($codeInstalled) {
    $vsCodeExtensions = @(
        'GitHub.copilot'                    # GitHub Copilot
        'GitHub.copilot-chat'               # Copilot Chat
        'saoudrizwan.claude-dev'            # Cline (Claude agent in VS Code)
        'continue.continue'                 # Continue (open-source AI assistant)
        'TabbyML.vscode-tabby'              # Tabby (self-hosted completion)
        'sourcegraph.cody-ai'               # Cody (Sourcegraph AI)
    )

    foreach ($ext in $vsCodeExtensions) {
        Write-Host "  Installing VS Code extension: $ext"
        code --install-extension $ext --force 2>$null
    }
    Write-Host "  VS Code AI extensions installed." -ForegroundColor Green
} else {
    Write-Host "  VS Code CLI not found — install VS Code first, then re-run." -ForegroundColor DarkGray
}

# ============================================================
# 4. Set up API key placeholders
# ============================================================
Write-Host "`n--- API key reminders ---" -ForegroundColor Yellow

Write-Host @"

  After setup, configure your API keys as environment variables:

    ANTHROPIC_API_KEY     — Claude API (claude.ai/settings)
    OPENAI_API_KEY        — OpenAI / ChatGPT (platform.openai.com)
    GITHUB_TOKEN          — GitHub Copilot (github.com/settings/tokens)
    GROQ_API_KEY          — Groq (console.groq.com)
    GOOGLE_API_KEY        — Gemini (aistudio.google.com)
    OPENROUTER_API_KEY    — OpenRouter (openrouter.ai)

  Set them permanently:
    [System.Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', 'sk-...', 'User')

  Or add to your PowerShell profile:
    notepad `$PROFILE

"@ -ForegroundColor White

# ============================================================
# 5. Chrome AI extensions
# ============================================================
Write-Host "--- Opening Chrome AI extensions ---" -ForegroundColor Yellow

$chromeAiExtensions = @(
    @{ Name = 'Claude (Anthropic)';     Url = 'https://chromewebstore.google.com/detail/claude/danfoibhepkflpmeinmfpiajkdccdanf' }
    @{ Name = 'ChatGPT (OpenAI)';       Url = 'https://chromewebstore.google.com/detail/chatgpt/jfbnmfeepmbpgiccfkopaadjpgjafhlc' }
    @{ Name = 'Monica AI';              Url = 'https://chromewebstore.google.com/detail/monica-your-ai-copilot/ofpnmcalabcbjgholdjcjblkibolbppb' }
)

foreach ($ext in $chromeAiExtensions) {
    Write-Host "  Opening $($ext.Name) ..."
    Start-Process $ext.Url
    Start-Sleep -Milliseconds 800
}

# ============================================================
# Summary
# ============================================================
Write-Host "`n=== AI & Agent Tools Setup Complete ===" -ForegroundColor Green

if ($failed.Count -gt 0) {
    Write-Host "`nFailed to install:" -ForegroundColor Red
    $failed | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}

Write-Host @"

  Next steps:
  1. Set your API keys (see above)
  2. Open Cursor/VS Code and sign in to Copilot
  3. Launch Ollama and pull a model: ollama pull llama3.1
  4. Run 'claude' in terminal to start Claude Code
  5. Run 'aider' in a git repo for AI pair programming

"@ -ForegroundColor White
