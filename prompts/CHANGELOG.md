# Prompts Changelog

## v2.0.0 — 2025-02-10

**Breaking change**: System prompt moved from inline code to file-based composition.

### Added
- `/prompts/system.md` — Hard rules, model policy, safety boundaries
- `/prompts/persona.md` — Voice, social behavior, idle mode
- `/prompts/trading_policy.md` — Paper trading constraints, PDT simulation
- `/prompts/room_context.md` — ROOM_CONTEXT injector documentation
- `/prompts/CHANGELOG.md` — This file
- `prompt_loader.py` — Runtime composer that reads and combines prompt files

### Removed
- Inline system prompt from `build_system_prompt()` in clawdbot.py
- Inline identity guard from `generate_and_respond()` in clawdbot.py
- Inline tool protocol from `generate_and_respond()` in clawdbot.py

### Changed
- System prompt is now composed from markdown files at runtime
- Prompt changes no longer require code edits — just edit the .md files
- Outbound sanitization consolidated into single function
- Idle self-talk moved to configured channel with 30-min rate limit
