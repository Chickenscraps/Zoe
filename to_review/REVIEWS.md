# Zoe V4 - Code Review & Improvement Hotspots

This folder contains copies of the core "import" files that represent the primary surface area for Zoe V4's intelligence, trading, and safety logic. These files are candidates for modularization, performance tuning, and logic hardening.

## Files for Review

### 1. `clawdbot.py`

- **Role**: Main orchestrator and Discord interface.
- **Review Focus**: Currently >1500 lines. Needs to be split into sub-modules (e.g., `events.py`, `commands.py`, `bot_setup.py`). The permission logic and generate_respond loop are complex and could be flattened.

### 2. `model_router.py`

- **Role**: Intelligence layer, Gemini escalation, and budget tracking.
- **Review Focus**: Re-verify the escalation heuristics. Ensure the budget reset logic is thread-safe for high-concurrency scenarios.

### 3. `trading_engine_v4.py`

- **Role**: Core options trading logic and broker integration.
- **Review Focus**: Needs more robust error handling for API timeouts. The P&L calculation logic is currently simplistic and could be deepened.

### 4. `renderer.py`

- **Role**: Playwright capture of shareable tickets.
- **Review Focus**: Resource management. Browser context pooling could be implemented to speed up concurrent renders.

### 5. `safety_layer/sanitize.py`

- **Role**: Outbound leakage protection.
- **Review Focus**: The regex list is effective but could be expanded. Consider an LLM-based "safety judge" for a second pass in high-stakes DMs.

### 6. `context/room_context.py`

- **Role**: Multi-user memory and Vibe detection.
- **Review Focus**: Expand keywords for better "tone" detection. The `room_summary` is currently template-based; consider using a small LLM call to summarize the last 10 messages for higher fidelity.

### 7. `media_utils.py`

- **Role**: Captioning and Tenor GIF selection.
- **Review Focus**: Enhance the `CaptionGenerator` to use more of Zoe's specific character traits (dark humor, ruthlessness).
