# Zoe ROOM_CONTEXT Injection & Safety Layer

Zoe is now context-aware and strictly sanitized to prevent internal leaks.

## Features

- **ROOM_CONTEXT**: The last 10 messages from the channel are injected into every LLM call as a JSON block.
- **Heuristics**: Automatically detects topic (trading, cleanup, debug, plan, banter) and tone (chill, chaotic, locked-in, hyped, neutral).
- **Inbound Sanitization**: Mentions, links, and newlines are stripped/flattened from history messages.
- **Outbound Execution (STRICT)**: All LLM responses are parsed through a regex-based safety filter that removes internal thoughts, tool traces, code blocks, and JSON blobs.
- **Runtime Buffer**: Uses a per-channel rolling `deque` for high-performance context retrieval without database overhead.

## New Modules

- `context/room_context.py`: Logic for building context objects and detecting vibe/topic.
- `safety_layer/sanitize.py`: Comprehensive regex filters for inbound and outbound text.

## Configuration

Ensure your `config.yaml` has the correct `admin_user_ids` to distinguish roles in the context object.
