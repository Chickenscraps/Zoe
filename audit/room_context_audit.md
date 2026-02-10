# ROOM_CONTEXT Audit Note

## Tech Stack

- **Language**: Python
- **Bot Lib**: `discord.py` (via `discord.ext.commands`)
- **LLM**: Gemini (via `model_router.py` and `gemini_backend.py`)

## Implementation Points

### 1. Message Handler

- **File**: `clawdbot.py`
- **Function**: `on_message(message: discord.Message)` (Line 280)
- **Role**: Maintain per-channel rolling buffer (deque) of sanitized messages.

### 2. LLM Call Wrapper

- **File**: `clawdbot.py`
- **Function**: `generate_and_respond(...)` (Line 505)
- **Role**: Build `ROOM_CONTEXT` object, inject into prompt, and call `sanitize_outbound_text`.

### 3. Gemini Backend

- **File**: `model_router.py` / `llm_backends/gemini_backend.py`
- **Role**: Execute the LLM call with the injected system/user prompts.

### 4. New Modules

- `context/room_context.py`: Logic for building the context object and heuristics.
- `safety/sanitize.py`: Inbound and outbound sanitization logic.

## Strategy

1. Implement `safety/sanitize.py` first.
2. Implement `context/room_context.py`.
3. Update `clawdbot.py` to maintain the buffer and inject context.
4. Update `clawdbot.py` to sanitize outbound responses.
