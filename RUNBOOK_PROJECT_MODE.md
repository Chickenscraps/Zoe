# 🚀 Zoe's Project Mode & Antigravity Router Runbook

This guide explains how to use the new "Project Mode" and LLM Router features in Clawdbot.

## 1. Setup & Configuration

Ensure `.env.secrets` in `C:\Users\josha\OneDrive\Desktop\Clawd` has these set:

```env
# Gemini Direct API (Required for LLM Routing)
GEMINI_API_KEY="AIzaSyDvEHSFyPnEJRO4_r5gRmpgRHn6JVNox6E"
```

### Start Clawdbot

No proxy setup required. Direct API access to Gemini.

### Restart Clawdbot

For changes to take effect:

```powershell
# Stop current instance (Ctrl+C)
python clawdbot.py
```

## 2. Using Project Mode

Project Mode allows Zoe to work on long-running coding tasks autonomously.

### Commands (Discord)

| Command                  | Description                     | Example                            |
| :----------------------- | :------------------------------ | :--------------------------------- |
| `/project new <name>`    | Create a new project folder     | `/project new "Portfolio Site"`    |
| `/project status <name>` | Check progress of a project     | `/project status "portfolio_site"` |
| `/project list`          | List all active projects        | `/project list`                    |
| `/project resume <name>` | Resume work (scheduler pick-up) | `/project resume "portfolio_site"` |

### Workflow

1. **Create**: Run `/project new "My App"`.
   - Creates `zoe_projects/my_app/` with `README.md`, `TASKS.md`, etc.
2. **Plan**: Edit `TASKS.md` manually or ask Zoe to plan (future).
   - _Current Implementation_: Add tasks to `project.json` "next_tasks" list manually for now, or rely on Zoe's default scaffolding.
3. **Execute**: The bot runs a "Work Unit" every 15 minutes.
   - It picks the top task from `next_tasks`.
   - Generates code via Antigravity Router.
   - Updates files and logs progress to `ARTIFACTS/progress_log.md`.
   - Posts a status update to the system channel.

## 3. Architecture Overview

### Model Router (`model_router.py`)

Handles LLM calls with smart Flash-Lite/Pro escalation:

1. **Default**: Gemini 2.0 Flash-Lite (cost-effective)
2. **Escalation**: Gemini 2.5 Pro (complex debugging/architecture)
3. **Fallback**: Local Ollama (emergency)

### Project Structure (`zoe_projects/`)

Each project gets a standardized layout:

```
my_project/
├── src/           # Source code
├── assets/        # Images/Data
├── docs/          # Documentation
├── ARTIFACTS/     # Logs & Outputs
├── project.json   # State tracking
└── tasks.md       # Task list
```

## 4. Troubleshooting

- **Bot not replying?** Check `GEMINI_API_KEY` validity in `.env.secrets`.
- **Projects not advancing?** Check `project.json` in the project folder. Ensure `status` is "active" or "in_progress" and `next_tasks` is not empty.
- **Logs**: Check console output for `♻️ Project Cycle Triggered`.

---

_Created by Zoe - 2026_
