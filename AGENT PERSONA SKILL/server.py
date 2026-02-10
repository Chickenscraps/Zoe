
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
import sys
import json
import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, Optional, List, Any

# Paths
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SKILL_DIR, ".."))

# Import local modules
if SKILL_DIR not in sys.path:
    sys.path.append(SKILL_DIR)

try:
    from structured_logger import logger
except ImportError:
    class MockLogger:
        def info(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
        def log_request(self, *args, **kwargs): pass
        def log_model_call(self, *args, **kwargs): pass
        def log_action(self, *args, **kwargs): pass
    logger = MockLogger()

try:
    if PROJECT_ROOT not in sys.path:
        sys.path.append(PROJECT_ROOT)
    from model_router import model_router
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

app = FastAPI(title="Clawdbot API", version="2.1.0")

# Enable CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics storage
class Metrics:
    def __init__(self):
        self.requests_total = 0
        self.requests_success = 0
        self.requests_failed = 0
        self.toasts_sent = 0
        self.gemini_calls = 0
        self.gemini_failures = 0
        self.gemini_latency_sum = 0.0
        self.last_success_times = {}
        self.start_time = datetime.now()
    
    def record_request(self, success: bool):
        self.requests_total += 1
        if success:
            self.requests_success += 1
        else:
            self.requests_failed += 1
    
    def record_gemini_call(self, latency_ms: float, success: bool):
        self.gemini_calls += 1
        self.gemini_latency_sum += latency_ms
        if not success:
            self.gemini_failures += 1
        else:
            self.last_success_times["gemini"] = datetime.now().isoformat()
    
    def record_toast(self):
        self.toasts_sent += 1
    
    def to_dict(self):
        return {
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "requests": {
                "total": self.requests_total,
                "success": self.requests_success,
                "failed": self.requests_failed
            },
            "llm": {
                "calls": self.gemini_calls,
                "failures": self.gemini_failures,
                "avg_latency_ms": self.gemini_latency_sum / max(1, self.gemini_calls)
            },
            "toasts_sent": self.toasts_sent,
            "last_success_times": self.last_success_times
        }

metrics = Metrics()

class ChatRequest(BaseModel):
    message: str
    user_id: str = "292890243852664855"  # Default to Josh

@app.get("/")
async def root():
    return {
        "status": "Clawdbot Backend Active",
        "version": "2.1.0",
        "endpoints": [
            "/chat", "/status", "/health", "/metrics", 
            "/explain/last", "/news/latest", "/showcase/list",
            "/logs/{mode}", "/mood/set", "/news/check"
        ]
    }

@app.get("/health")
async def health():
    """Health check with dependency status."""
    dependencies = {}
    
    # Resilience
    try:
        from resilience import gemini_breaker
        dependencies["resilience"] = {
            "status": "ok" if gemini_breaker.state == "CLOSED" else "degraded",
            "circuit_state": gemini_breaker.state
        }
    except ImportError:
        dependencies["resilience"] = {"status": "unknown"}
    
    # Gemini (via ModelRouter)
    if GENAI_AVAILABLE:
        dependencies["gemini"] = {"status": "ok"}
    else:
        dependencies["gemini"] = {"status": "error", "error": "model_router missing"}
    
    # Modules
    for module in ["mood_engine", "news_watcher", "discord_bridge", "affect_engine"]:
        try:
            # Simple check if module can be imported
            __import__(module)
            dependencies[module] = {"status": "loaded"}
        except ImportError:
            dependencies[module] = {"status": "missing"}
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "dependencies": dependencies
    }

@app.get("/metrics")
async def get_metrics():
    """Get system metrics."""
    return metrics.to_dict()

@app.get("/status")
async def get_status():
    """Get full system status."""
    state = {}
    
    # Mood
    try:
        from mood_engine import mood_engine
        state["mood"] = mood_engine.get_status()
    except:
        state["mood"] = None
    
    # News
    try:
        from news_watcher import news_watcher
        state["news"] = news_watcher.get_status()
    except:
        state["news"] = None
        
    # Affect
    try:
        from affect_engine import affect_engine
        state["affect"] = affect_engine.get_status()
    except:
        state["affect"] = None
        
    # Discord
    try:
        from discord_bridge import discord_bridge
        state["discord"] = discord_bridge.get_status()
    except:
        state["discord"] = None
        
    # Showcase
    try:
        from showcase_manager import showcase_manager
        state["showcase"] = showcase_manager.get_status()
    except:
        state["showcase"] = None
    
    state["uptime"] = metrics.to_dict()["uptime_seconds"]
    
    return state

@app.get("/explain/last")
async def explain_last():
    """Get rationale for last decision."""
    try:
        from explainability import get_last_rationale
        return get_last_rationale() or {"message": "No rationale found"}
    except ImportError:
        return {"error": "Explainability module missing"}

@app.get("/news/latest")
async def get_latest_news():
    """Get latest news pulse."""
    try:
        from news_watcher import news_watcher
        pulse = news_watcher.get_cached_pulse()
        if not pulse:
            return {"status": "no_news"}
        return pulse
    except ImportError:
        raise HTTPException(status_code=501, detail="News module missing")

@app.get("/showcase/list")
async def list_showcases():
    """List pending and ready showcases."""
    try:
        from showcase_manager import showcase_manager
        return {
            "pending": [c.to_dict() for c in showcase_manager.get_pending()],
            "ready": [c.to_dict() for c in showcase_manager.get_ready()]
        }
    except ImportError:
        return {"pending": [], "ready": []}
        
@app.post("/showcase/send/{id}")
async def send_showcase_endpoint(id: str):
    """Trigger sending a ready showcase."""
    try:
        from showcase_manager import send_showcase
        success, msg = send_showcase(id, ping=False)
        if success:
            return {"status": "sent", "message": msg}
        else:
            raise HTTPException(status_code=400, detail=msg)
    except ImportError:
        raise HTTPException(status_code=501, detail="Showcase manager missing")

@app.get("/logs/{mode}")
async def get_logs(mode: str):
    log_file = os.path.join(SKILL_DIR, f"journal_{mode}.jsonl")
    if not os.path.exists(log_file):
        # Fallback to structured log
        if mode == "structured":
            log_file = os.path.join(SKILL_DIR, "clawdbot_structured.jsonl")
        else:
            return {"logs": []}
            
    if not os.path.exists(log_file):
        return {"logs": []}
    
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
            logs = []
            for line in lines[-50:]:
                try:
                    logs.append(json.loads(line))
                except: continue
            return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mood/set")
async def set_mood(mood: str):
    """Manually set mood (for testing)."""
    try:
        from mood_engine import mood_engine, InternalMood
        
        # Valid values check could go here
        mood_engine._transition_mood(natural=False, target=mood)
        return {"status": "ok", "new_mood": mood_engine.get_current_mood()}
    except ImportError:
        raise HTTPException(status_code=501, detail="Mood engine not available")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/news/check")
async def trigger_news_check():
    """Manually trigger a news check."""
    try:
        from news_watcher import news_watcher
        pulse = news_watcher.fetch_headlines()
        return {
            "status": "ok", 
            "items_count": len(pulse.items) if pulse else 0,
            "summary": pulse.summary if pulse else "No news"
        }
    except ImportError:
        raise HTTPException(status_code=501, detail="News watcher not available")

# Model Config


@app.post("/chat")
async def chat(request: ChatRequest):
    correlation_id = str(uuid.uuid4())
    start_time = time.time()
    
    # 1. Log Request
    logger.log_request(request.message, correlation_id)
    
    # 2. Check Slash Commands (WSB / Idea Vault)
    if request.message.startswith("/"):
        cmd_parts = request.message.split()
        cmd = cmd_parts[0].lower()
        
        response_text = None
        
        try:
            if cmd == "/wsb":
                from workstream_manager import workstream_manager
                sub = cmd_parts[1].lower() if len(cmd_parts) > 1 else "show"
                
                if sub == "show":
                    active = workstream_manager.get_all_active()
                    lines = ["**Workstream Board**"]
                    for slot, data in active.items():
                        lines.append(f"**{slot}**: {data.get('title')} ({data.get('owner')})")
                        if data.get('next_actions'):
                            lines.append(f"  Next: {data['next_actions'][0]}")
                    response_text = "\n".join(lines)
                    
                elif sub == "focus" and len(cmd_parts) > 2:
                    slot = cmd_parts[2].upper()
                    # Logic to set focus (simplified)
                    response_text = f"Focused on {slot} (Not fully impl in command yet)"
                    
            elif cmd == "/project" and len(cmd_parts) > 2:
                if cmd_parts[1].lower() == "journal":
                    slug = cmd_parts[2]
                    from project_journal import ProjectJournal
                    pj = ProjectJournal(slug)
                    response_text = f"**Journal: {slug}**\n\n{pj.get_section('Next Actions')}"
                    
            elif cmd == "/idea" and len(cmd_parts) > 2:
                if cmd_parts[1].lower() == "add":
                    title = " ".join(cmd_parts[2:])
                    from idea_vault import idea_vault
                    idea_vault.add_idea(title, "Via Chat Command")
                    response_text = f"Idea added: *{title}*"
                    
            elif cmd == "/idle":
                 response_text = "Idle mode settings updated (Simulation)"
                 
        except Exception as e:
            response_text = f"Command error: {str(e)}"
            
        if response_text:
            metrics.record_request(True)
            return {"response": response_text, "correlation_id": correlation_id}

    # 3. Check Dispatcher (Legacy)
    text_lower = request.message.lower()
    needs_dispatcher = any(k in text_lower for k in [
        "see my", "look at", "sweep", "confirm", "do it", "screen", 
        "calendar", "events", "email", "files", "tasks"
    ])
    
    if needs_dispatcher:
        try:
            dispatcher_path = os.path.join(PROJECT_ROOT, "dispatcher.py")
            cmd = [sys.executable, dispatcher_path, request.message]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Extract response from stdout
            response_text = "Action executed."
            for line in reversed(result.stdout.splitlines()):
                if line.strip().startswith("RESPONSE:"):
                    response_text = line.replace("RESPONSE:", "").strip()
                    break
            
            logger.log_action("dispatcher", "exec", "User command", correlation_id)
            metrics.record_request(True)
            
            # Store Rationale
            try:
                from explainability import store_rationale
                store_rationale("dispatcher_command", "User input matched command keywords", 
                              {"input": request.message}, 1.0, correlation_id)
            except: pass
            
            return {"response": response_text, "correlation_id": correlation_id}
        except Exception as e:
            logger.error("dispatcher.failed", str(e), correlation_id)

    # 3. Check Degraded Mode
    try:
        from resilience import gemini_breaker
        if gemini_breaker.state == "OPEN":
            from degraded_mode import get_fallback_response
            response = get_fallback_response(request.message)
            metrics.record_request(True)
            return {"response": response, "correlation_id": correlation_id, "mode": "degraded"}
    except: pass

    # 4. LLM Generation
    try:
        # Context Loading
        from memory_store import get_memory_context
        try:
            from persona_loader import get_personalized_system_prompt
            discord_user_id = request.user_id
            sys_prompt = get_personalized_system_prompt(discord_user_id)
        except:
            sys_prompt = "You are Clawdbot."
            
        # Relationship Context (Multi-User)
        try:
            from relationship_manager import RelationshipManager
            rm = RelationshipManager()
            rel_context = rm.get_relationship_context(request.user_id)
            sys_prompt += f"\n\n[RELATIONSHIP CONTEXT]\n{rel_context}"
        except ImportError:
            pass
            
        # Mood Context
        try:
            from mood_engine import mood_engine
            mood = mood_engine.get_status()
            sys_prompt += f"\n[Current Mood: {mood['display_mood']} - {mood.get('mask_status', '')}]"
        except: pass
        
        # Memory Context (User Specific)
        # We need to update get_memory_context to accept user_id or handle it here
        # For now, let's just append recent activities if get_memory_context is global
        # memory = get_memory_context() 
        # Actually better to update memory_store.py's helper or just call it directly
        from memory_store import memory as mem_store
        recent_acts = mem_store.get_recent_activities(limit=5, user_id=request.user_id)
        memory_str = json.dumps(recent_acts, indent=2)
        

        # Call Gemini (via ModelRouter)
        if GENAI_AVAILABLE:
            # ModelRouter defaults to Gemini Flash/Pro dynamically
            # We construct messages format expected by ModelRouter (list of dicts)
            
            # Combine System Prompts
            full_system_prompt = f"{sys_prompt}\n\n[MEMORY]\nRecent Activities:\n{memory_str}"
            
            messages = [{'role': 'user', 'content': request.message}]
            
            response_text = await model_router.chat(
                messages=messages,
                system=full_system_prompt,
                model="gemini-2.0-flash-lite" # Default to fast model for chat
            )
            
            latency = (time.time() - start_time) * 1000
            metrics.record_gemini_call(latency, True)
            logger.log_model_call("gemini-2.0-flash-lite", request.message, response_text, latency, True, correlation_id)
            
            # Store Rationale
            try:
                from explainability import store_rationale
                store_rationale("llm_reply", "Generated response via Gemini", 
                              {"model": "gemini-2.0-flash-lite"}, 0.9, correlation_id)
            except: pass

            metrics.record_request(True)
            return {"response": response_text, "correlation_id": correlation_id}
        else:
            return {"response": "Gemini Router not available.", "correlation_id": correlation_id}

    except Exception as e:
        latency = (time.time() - start_time) * 1000
        metrics.record_gemini_call(latency, False)
        metrics.record_request(False)
        logger.error("chat.failed", str(e), correlation_id)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("🚀 Clawdbot v2.1 API starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
