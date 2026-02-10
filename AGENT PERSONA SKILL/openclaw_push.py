#!/usr/bin/env python3
"""
OpenClaw Gateway Push Client
Based on OpenClaw Gateway Protocol v3.
https://docs.openclaw.ai/gateway/protocol
"""

import asyncio
import json
import os
import time
import uuid
import hashlib

try:
    import websockets
except ImportError:
    print("websockets not installed. Installing...")
    import subprocess
    subprocess.check_call(["pip", "install", "websockets"])
    import websockets

# Gateway settings
GATEWAY_URL = os.environ.get("OPENCLAW_GATEWAY_URL", "ws://127.0.0.1:18789/ws")
TOKEN = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "7951895c62cb268df323f0846a65f27e0e995ddc26864fbf")

# Generate a device fingerprint
DEVICE_ID = hashlib.sha256(f"clawdbot-proactive-{os.getlogin()}".encode()).hexdigest()[:32]

async def push_message(message: str, session_key: str = "agent:main:main") -> bool:
    """
    Push a message to the OpenClaw gateway.
    Uses the official OpenClaw WebSocket protocol v3.
    """
    try:
        async with websockets.connect(GATEWAY_URL) as ws:
            # Step 1: Receive connect.challenge event
            first_msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            challenge_data = json.loads(first_msg)
            
            if challenge_data.get("event") != "connect.challenge":
                print(f"Expected connect.challenge, got: {challenge_data}")
                # Some local setups may skip challenge
            
            challenge_nonce = challenge_data.get("payload", {}).get("nonce", "local")
            
            # Step 2: Send connect request with full protocol
            connect_id = str(uuid.uuid4())
            connect_req = {
                "type": "req",
                "id": connect_id,
                "method": "connect",
                "params": {
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {
                        "id": "clawdbot-proactive",
                        "version": "1.0.0",
                        "platform": "windows",
                        "mode": "operator"
                    },
                    "role": "operator",
                    "scopes": ["operator.read", "operator.write"],
                    "caps": [],
                    "commands": [],
                    "permissions": {},
                    "auth": {"token": TOKEN},
                    "locale": "en-US",
                    "userAgent": "clawdbot-proactive/1.0.0",
                    "device": {
                        "id": DEVICE_ID,
                        "nonce": challenge_nonce
                    }
                }
            }
            await ws.send(json.dumps(connect_req))
            
            # Wait for connect response (hello-ok)
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            resp_data = json.loads(response)
            
            if resp_data.get("type") != "res" or not resp_data.get("ok"):
                print(f"Connect failed: {resp_data}")
                return False
            
            print(f"Connected: {resp_data.get('payload', {}).get('type')}")
            
            # Step 3: Send chat.send request
            send_id = str(uuid.uuid4())
            idempotency_key = f"proactive-{int(time.time()*1000)}"
            
            chat_req = {
                "type": "req",
                "id": send_id,
                "method": "chat.send",
                "params": {
                    "sessionKey": session_key,
                    "message": message,
                    "idempotencyKey": idempotency_key
                }
            }
            await ws.send(json.dumps(chat_req))
            
            # Wait for send response
            response = await asyncio.wait_for(ws.recv(), timeout=10.0)
            resp_data = json.loads(response)
            
            if resp_data.get("type") == "res" and resp_data.get("ok"):
                print(f"Message sent: {resp_data.get('payload', {})}")
                return True
            else:
                print(f"Send failed: {resp_data}")
                return False
            
    except asyncio.TimeoutError:
        print("WebSocket timeout")
        return False
    except Exception as e:
        print(f"Push error: {e}")
        import traceback
        traceback.print_exc()
        return False

def push_notification_sync(message: str, session_key: str = "agent:main:main") -> bool:
    """Synchronous wrapper for push_message."""
    try:
        return asyncio.run(push_message(message, session_key))
    except Exception as e:
        print(f"Sync push error: {e}")
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
        success = push_notification_sync(msg)
        print(f"Push {'succeeded' if success else 'failed'}")
    else:
        # Test message
        success = push_notification_sync("🦞 [Clawdbot] Test notification push!")
        print(f"Test push {'succeeded' if success else 'failed'}")
