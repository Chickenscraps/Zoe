"""
Host Bridge Service - Windows Native API for WSL2 Agent
Exposes localhost-only tools for audio, vision, OS control, and filesystem access.

Run on Windows: python host_bridge.py
"""
import os
import json
import asyncio
import subprocess
import base64
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ============================================================================
# Configuration
# ============================================================================

HOST = "127.0.0.1"
PORT = 9876
SECRET_TOKEN = os.environ.get("HOST_BRIDGE_SECRET", "clawdbot-local-dev")

# Allowlists for safety
POWERSHELL_ALLOWLIST = [
    "Get-Process",
    "Get-Service",
    "Get-ChildItem",
    "Get-Content",
    "Get-Date",
    "Get-ComputerInfo",
    "Test-Connection",
    "Resolve-DnsName",
    # Game server commands
    "Start-Process",
    "Stop-Process",
    "Get-NetTCPConnection",
]

FS_ALLOWLIST_DIRS = [
    Path(os.path.expanduser("~")) / "OneDrive" / "Desktop" / "Clawd",
    Path("C:/Clawdbot/workspace"),
    Path("C:/Clawdbot/logs"),
    Path("C:/Clawdbot/game_servers"),
]

AUDIT_LOG_PATH = Path(os.path.expanduser("~")) / "OneDrive" / "Desktop" / "Clawd" / "logs" / "tool_audit.jsonl"

# ============================================================================
# App Setup
# ============================================================================

app = FastAPI(
    title="Clawdbot Host Bridge",
    description="Windows-native tools for WSL2 agent",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:*", "http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Auth & Audit
# ============================================================================

async def verify_token(authorization: str = Header(None)):
    """Simple shared-secret auth."""
    if authorization != f"Bearer {SECRET_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid token")
    return True

def audit_log(tool: str, args: dict, reason: str, result: dict):
    """Log all tool calls for transparency."""
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "tool": tool,
        "args": args,
        "reason": reason,
        "result": result
    }
    
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

# ============================================================================
# Request/Response Models
# ============================================================================

class AudioListenRequest(BaseModel):
    duration_ms: int = 5000
    reason: str = "User request"

class VisionGlanceRequest(BaseModel):
    include_frame: bool = False
    reason: str = "User request"

class PowerShellRequest(BaseModel):
    cmd: str
    cwd: Optional[str] = None
    timeout_s: int = 30
    reason: str = "User request"

class UIActionRequest(BaseModel):
    actions: list[dict]
    reason: str = "User request"

class FSReadRequest(BaseModel):
    path: str
    reason: str = "User request"

class FSWriteRequest(BaseModel):
    path: str
    content: str
    reason: str = "User request"

# ============================================================================
# Safety Checks
# ============================================================================

def is_powershell_allowed(cmd: str) -> bool:
    """Check if PowerShell command is in allowlist."""
    cmd_lower = cmd.lower().strip()
    for allowed in POWERSHELL_ALLOWLIST:
        if cmd_lower.startswith(allowed.lower()):
            return True
    return False

def is_path_allowed(path: str) -> bool:
    """Check if filesystem path is in allowed directories."""
    try:
        target = Path(path).resolve()
        for allowed_dir in FS_ALLOWLIST_DIRS:
            try:
                if target.is_relative_to(allowed_dir.resolve()):
                    return True
            except:
                pass
    except:
        pass
    return False

# ============================================================================
# Endpoints
# ============================================================================

@app.get("/")
async def root():
    return {
        "service": "Clawdbot Host Bridge",
        "status": "running",
        "version": "1.0.0",
        "tools": ["audio.listen", "vision.glance", "os.powershell", "os.ui", "fs.read", "fs.write"]
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/audio/listen")
async def audio_listen(req: AudioListenRequest, _: bool = Depends(verify_token)):
    """
    Listen via microphone for specified duration.
    Returns transcript + VAD events + stress markers.
    
    NOTE: Full implementation requires sounddevice + whisper.
    This is a placeholder that returns mock data.
    """
    result = {
        "transcript": "",
        "vad_events": [],
        "stress_marker": 0.0,
        "confidence": 0.0,
        "status": "sensor_not_enabled",
        "message": "Audio listening requires explicit user consent. Use /mic to enable."
    }
    
    audit_log("audio.listen", {"duration_ms": req.duration_ms}, req.reason, result)
    return result


@app.post("/vision/glance")
async def vision_glance(req: VisionGlanceRequest, _: bool = Depends(verify_token)):
    """
    Capture webcam frame and analyze presence/engagement.
    
    NOTE: Full implementation requires opencv + mediapipe.
    This is a placeholder that returns mock data.
    """
    result = {
        "presence_detected": False,
        "engagement_level": 0.0,
        "valence": 0.5,
        "arousal": 0.5,
        "frame_b64": None,
        "status": "sensor_not_enabled",
        "message": "Vision requires explicit user consent. Use /camera to enable."
    }
    
    audit_log("vision.glance", {"include_frame": req.include_frame}, req.reason, result)
    return result


@app.post("/os/powershell")
async def os_powershell(req: PowerShellRequest, _: bool = Depends(verify_token)):
    """
    Execute allowlisted PowerShell command.
    """
    if not is_powershell_allowed(req.cmd):
        result = {
            "success": False,
            "error": f"Command not in allowlist: {req.cmd}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1
        }
        audit_log("os.powershell", {"cmd": req.cmd}, req.reason, result)
        raise HTTPException(status_code=403, detail=result["error"])
    
    try:
        process = subprocess.run(
            ["powershell", "-Command", req.cmd],
            capture_output=True,
            text=True,
            timeout=req.timeout_s,
            cwd=req.cwd
        )
        
        result = {
            "success": process.returncode == 0,
            "stdout": process.stdout[:10000],  # Limit output size
            "stderr": process.stderr[:2000],
            "exit_code": process.returncode
        }
    except subprocess.TimeoutExpired:
        result = {
            "success": False,
            "error": f"Command timed out after {req.timeout_s}s",
            "stdout": "",
            "stderr": "",
            "exit_code": -1
        }
    except Exception as e:
        result = {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": "",
            "exit_code": -1
        }
    
    audit_log("os.powershell", {"cmd": req.cmd, "cwd": req.cwd}, req.reason, result)
    return result


@app.post("/os/ui")
async def os_ui(req: UIActionRequest, _: bool = Depends(verify_token)):
    """
    Execute UI automation sequence.
    
    NOTE: Full implementation requires pywinauto.
    This is a placeholder.
    """
    result = {
        "success": False,
        "message": "UI automation not yet implemented",
        "actions_attempted": len(req.actions),
        "screenshot_b64": None
    }
    
    audit_log("os.ui", {"actions": req.actions}, req.reason, result)
    return result


@app.post("/fs/read")
async def fs_read(req: FSReadRequest, _: bool = Depends(verify_token)):
    """
    Read file from allowlisted directory.
    """
    if not is_path_allowed(req.path):
        result = {
            "success": False,
            "error": f"Path not in allowlist: {req.path}",
            "content": None
        }
        audit_log("fs.read", {"path": req.path}, req.reason, result)
        raise HTTPException(status_code=403, detail=result["error"])
    
    try:
        with open(req.path, "r", encoding="utf-8") as f:
            content = f.read()
        
        result = {
            "success": True,
            "content": content[:100000],  # Limit size
            "size_bytes": len(content)
        }
    except Exception as e:
        result = {
            "success": False,
            "error": str(e),
            "content": None
        }
    
    audit_log("fs.read", {"path": req.path}, req.reason, result)
    return result


@app.post("/fs/write")
async def fs_write(req: FSWriteRequest, _: bool = Depends(verify_token)):
    """
    Write file to allowlisted directory.
    """
    if not is_path_allowed(req.path):
        result = {
            "success": False,
            "error": f"Path not in allowlist: {req.path}"
        }
        audit_log("fs.write", {"path": req.path}, req.reason, result)
        raise HTTPException(status_code=403, detail=result["error"])
    
    try:
        # Ensure parent directory exists
        Path(req.path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(req.path, "w", encoding="utf-8") as f:
            f.write(req.content)
        
        result = {
            "success": True,
            "bytes_written": len(req.content)
        }
    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
    
    audit_log("fs.write", {"path": req.path}, req.reason, result)
    return result


@app.get("/audit/recent")
async def get_recent_audit(_: bool = Depends(verify_token)):
    """Get recent audit log entries."""
    if not AUDIT_LOG_PATH.exists():
        return {"entries": []}
    
    with open(AUDIT_LOG_PATH, "r") as f:
        lines = f.readlines()[-50:]  # Last 50 entries
    
    entries = [json.loads(line) for line in lines if line.strip()]
    return {"entries": entries}


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Clawdbot Host Bridge Service")
    print("=" * 60)
    print(f"  Binding to: http://{HOST}:{PORT}")
    print(f"  Auth token: {SECRET_TOKEN[:8]}...")
    print(f"  Audit log:  {AUDIT_LOG_PATH}")
    print("=" * 60)
    
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
