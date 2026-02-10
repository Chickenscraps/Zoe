
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
import sys
import json

# Paths
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", ".."))

# Import local modules
if SKILL_DIR not in sys.path:
    sys.path.append(SKILL_DIR)

try:
    from journal_logger import log_event, get_log_file
except ImportError:
    def log_event(*args, **kwargs): pass

app = FastAPI()

# Enable CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.get("/")
async def root():
    return {"status": "Clawdbot Backend is active", "ui_url": "http://localhost:5173"}

@app.get("/status")
async def get_status():
    state_file = os.path.join(SKILL_DIR, "state.json")
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            return json.load(f)
    return {"mode": "normal", "pending_action": None}

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        dispatcher_path = os.path.join(PROJECT_ROOT, "dispatcher.py")
        cmd = ["python", dispatcher_path, request.message]
        
        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        
        response_text = result.stdout.strip() if result.stdout else "No response from agent."
        if result.stderr and result.returncode != 0:
            print(f"Dispatcher Error: {result.stderr}")
            
        return {"response": response_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs/{mode}")
async def get_logs(mode: str):
    log_file = os.path.join(SKILL_DIR, f"journal_{mode}.jsonl")
    if not os.path.exists(log_file):
        return {"logs": []}
    
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
            logs = [json.loads(line) for line in lines[-50:]] # Last 50 entries
            return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("🚀 Clawdbot UI Backend starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
