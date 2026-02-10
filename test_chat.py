#!/usr/bin/env python3
"""Quick test of OpenClaw chat via WebSocket."""
import os

GATEWAY_URL = "ws://127.0.0.1:18789/ws"
TOKEN = os.environ.get("OPENCLAW_TEST_TOKEN", "REPLACE_WITH_YOUR_TOKEN")

print("Connecting to gateway...")
ws = websocket.create_connection(GATEWAY_URL, timeout=10)

# First message should be connect event
msg = json.loads(ws.recv())
print(f"Initial: type={msg.get('type')}, event={msg.get('event')}")

# Send hello
hello_id = str(uuid.uuid4())[:8]
hello_req = {
    "id": hello_id,
    "method": "hello",
    "params": {
        "token": TOKEN,
        "client": {"type": "test-chat", "version": "1.0.0"}
    }
}
ws.send(json.dumps(hello_req))
print("Sent hello, waiting for response...")

# Wait for hello response
while True:
    raw = ws.recv()
    if not raw.strip():
        continue
    msg = json.loads(raw)
    print(f"  Got: type={msg.get('type')}, id={msg.get('id')}, event={msg.get('event')}")
    if msg.get("id") == hello_id:
        print(f"  Hello ok: {msg.get('ok')}")
        if not msg.get("ok"):
            print(f"  Error: {msg.get('error')}")
            ws.close()
            exit(1)
        break

# Send chat
run_id = str(uuid.uuid4())[:8]
chat_req = {
    "id": run_id,
    "method": "chat.send",
    "params": {
        "sessionKey": "test-voice",
        "message": "Say hello in exactly 5 words",
        "idempotencyKey": run_id
    }
}
print(f"\nSending chat: {chat_req['params']['message']}")
ws.send(json.dumps(chat_req))

# Wait for response
response_text = ""
start_time = time.time()
timeout = 120

print("Waiting for response (max 120s)...")
while time.time() - start_time < timeout:
    try:
        ws.settimeout(2.0)
        raw = ws.recv()
        if not raw.strip():
            continue
        msg = json.loads(raw)
        
        msg_type = msg.get("type")
        event = msg.get("event")
        
        if msg_type == "response":
            print(f"  Response: ok={msg.get('ok')}, payload={str(msg.get('payload'))[:100]}")
        
        if event == "chat":
            payload = msg.get("payload", {})
            state = payload.get("state")
            
            if state == "delta":
                delta = payload.get("text", "")
                response_text += delta
                print(f"  Delta: '{delta}'")
            elif state == "final":
                if "message" in payload:
                    content = payload["message"].get("content", [])
                    for c in content:
                        if c.get("type") == "text":
                            response_text = c.get("text", response_text)
                print(f"\n{'='*50}\nFINAL RESPONSE:\n{response_text}\n{'='*50}")
                break
            elif state == "error":
                print(f"ERROR: {payload.get('errorMessage')}")
                break
    except websocket.WebSocketTimeoutException:
        print(".", end="", flush=True)
        continue
    except json.JSONDecodeError as e:
        print(f"  JSON error: {e}")
        continue
    except Exception as e:
        print(f"  Error: {e}")
        break

ws.close()
print("\nDone.")
