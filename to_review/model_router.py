"""
Model Router Module (Gemini Only)
Routes LLM requests to appropriate Gemini models with smart escalation.

Routing Hierarchy:
1. Gemini Flash-Lite (default - cost-effective)
2. Gemini Pro (escalation - complex/debugging tasks)
"""
import os
import json
import time
import asyncio
import logging
import hashlib
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

# Configure logging
logger = logging.getLogger(__name__)

class EscalationTracker:
    """Tracks task failures to determine when to escalate to Pro model."""
    
    def __init__(self):
        self.task_failures = defaultdict(int)  # task_hash → consecutive_failures
        self.last_success_model = {}  # task_hash → model_used
        self.escalation_keywords = [
            "stack trace", "traceback", "error:", "exception:",
            "dependency", "architecture", "design pattern",
            "circular import", "cannot import", "modulenotfounderror"
        ]
    
    def record_failure(self, task_hash: str, model: str, error_msg: str) -> None:
        """Record a task failure."""
        self.task_failures[task_hash] += 1
        logger.warning(f"⚠️ Task {task_hash[:8]} failed on {model} (attempt {self.task_failures[task_hash]})")
    
    def record_success(self, task_hash: str, model: str) -> None:
        """Record a successful completion."""
        self.task_failures[task_hash] = 0
        self.last_success_model[task_hash] = model
        logger.info(f"✅ Task {task_hash[:8]} succeeded with {model}")
    
    def should_escalate(self, task_hash: str, task_content: str, current_model: str) -> bool:
        """
        Determine if we should escalate from Flash-Lite to Pro.
        """
        if "pro" in current_model.lower():
            return False
        
        # 1. Flash-Lite failed 2 attempts
        if self.task_failures[task_hash] >= 2:
            return True, "consecutive_failures"
        
        # 2. Complexity check
        task_lower = task_content.lower()
        
        # Architecture / Multi-file / Test repair
        complexity_keywords = [
            "architecture", "refactor", "multi-file", "dependency", 
            "structure", "design pattern", "unit test", "failing test", "repair"
        ]
        if any(kw in task_lower for kw in complexity_keywords):
            return True, "complexity_detected"
            
        # 3. Safety-critical logic
        safety_keywords = [
            "risk limit", "pdt", "broker simulation", "equity", "simulation", 
            "trading_engine", "paper_broker", "security", "vault"
        ]
        if any(kw in task_lower for kw in safety_keywords):
            return True, "safety_critical_logic"
        
        return False, None
    
    def should_downgrade(self, task_hash: str) -> bool:
        """Determine if we should return from Pro to Flash-Lite."""
        last_model = self.last_success_model.get(task_hash, "")
        if "pro" in last_model.lower() and self.task_failures[task_hash] == 0:
            logger.info(f"🔻 Downgrading: Pro solved issue, returning to Flash-Lite")
            return True
        return False


class PromptCache:
    """Simple prompt cache to reduce redundant API calls."""
    
    def __init__(self, ttl_minutes: int = 10):
        self.cache = {}  # hash → (response, expiry_time)
        self.ttl = timedelta(minutes=ttl_minutes)
    
    def get(self, messages: List[Dict]) -> Optional[str]:
        """Get cached response if available and not expired."""
        cache_key = self._hash_messages(messages)
        if cache_key in self.cache:
            response, expiry = self.cache[cache_key]
            if datetime.now() < expiry:
                logger.info(f"💾 Cache hit ({cache_key[:8]})")
                return response
            else:
                del self.cache[cache_key]
        return None
    
    def set(self, messages: List[Dict], response: str) -> None:
        """Cache a response."""
        cache_key = self._hash_messages(messages)
        self.cache[cache_key] = (response, datetime.now() + self.ttl)
        logger.debug(f"💾 Cached response ({cache_key[:8]})")
    
    def _hash_messages(self, messages: List[Dict]) -> str:
        """Create hash of messages for cache key."""
        msg_str = json.dumps(messages, sort_keys=True)
        return hashlib.sha256(msg_str.encode()).hexdigest()


class ModelRouter:
    """Routes chat completion requests with smart escalation (Gemini Only)."""
    
    def __init__(self):
        self.flash_lite_model = "gemini-2.5-flash-lite"
        self.pro_model = "gemini-2.5-pro"
        self.current_model = self.flash_lite_model
        self.escalation_tracker = EscalationTracker()
        self.cache = PromptCache(ttl_minutes=10)
        
        # Pro budget
        self.pro_calls_count = 0
        self.pro_daily_budget = 50
        self.last_budget_reset = datetime.now().date()
        
        # Try to initialize Gemini backend
        try:
            from llm_backends import get_backend
            self.gemini_backend = get_backend()
            self.gemini_available = True
            logger.info("✅ Gemini backend ready")
        except Exception as e:
            logger.error(f"❌ Gemini backend failed to initialize: {e}")
            self.gemini_backend = None
            self.gemini_available = False
            # In Strict Mode, we do NOT fallback. System is effectively down for LLM.

    def _check_budget(self):
        """Reset budget daily and check if Pro is allowed."""
        today = datetime.now().date()
        if today > self.last_budget_reset:
            self.pro_calls_count = 0
            self.last_budget_reset = today
        
        return self.pro_calls_count < self.pro_daily_budget

    def _log_escalation(self, from_model: str, to_model: str, reason: str, correlation_id: str):
        """Log escalation to Supabase audit_log."""
        try:
            from supabase_memory import supabase_memory
            if not supabase_memory or not supabase_memory.client:
                return
            
            payload = {
                "action": "model_escalation",
                "actor": "model_router",
                "details": {
                    "from": from_model,
                    "to": to_model,
                    "reason": reason,
                    "correlation_id": correlation_id
                },
                "timestamp": datetime.now().isoformat()
            }
            supabase_memory.client.table("audit_log").insert(payload).execute()
            logger.info(f"📢 Scalation logged: {to_model} ({reason})")
        except Exception as e:
            logger.warning(f"⚠️ Failed to log escalation to audit_log: {e}")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 3,
        model: Optional[str] = None,
        force_pro: bool = False
    ) -> str:
        """
        Execute a chat completion with smart routing.
        Gemini Only. No local fallback.
        """
        # Prepend system prompt if provided
        if system:
            if not messages or messages[0].get('role') != 'system':
                messages = [{'role': 'system', 'content': system}] + messages
        
        # Check cache first
        cached = self.cache.get(messages)
        if cached:
            return cached
        
        # Generate task hash for escalation tracking
        task_content = " ".join(msg.get('content', '') for msg in messages)
        task_hash = hashlib.sha256(task_content.encode()).hexdigest()
        
        # Determine which model to use
        target_model = self.flash_lite_model
        correlation_id = str(uuid.uuid4())
        
        if model:
            target_model = model
            logger.info(f"Targeting explicit model: {target_model}")
        else:
            should_esc, reason = self.escalation_tracker.should_escalate(task_hash, task_content, self.current_model)
            if force_pro or should_esc:
                if self._check_budget():
                    target_model = self.pro_model
                    self._log_escalation(self.flash_lite_model, self.pro_model, reason or "force_pro", correlation_id)
                    self.pro_calls_count += 1
                else:
                    logger.warning("🔺 Pro budget exceeded. Falling back to Flash-Lite.")
                    target_model = self.flash_lite_model
            else:
                target_model = self.flash_lite_model
        
        # Execute Gemini
        if self.gemini_available:
            try:
                response = await self.gemini_backend.generate_text(
                    messages=messages,
                    model=target_model,
                    temperature=temperature,
                    retries=max_retries
                )
                
                # Record success
                self.escalation_tracker.record_success(task_hash, target_model)
                self.cache.set(messages, response)
                return response
                
            except Exception as e:
                logger.error(f"❌ Gemini failed ({target_model}): {e}")
                self.escalation_tracker.record_failure(task_hash, target_model, str(e))
                
                # Try escalation if we were on Flash-Lite
                if target_model == self.flash_lite_model:
                    logger.info("🔺 Attempting Pro escalation after Flash-Lite failure...")
                    try:
                        response = await self.gemini_backend.generate_text(
                            messages=messages,
                            model=self.pro_model,
                            temperature=temperature,
                            retries=1
                        )
                        self.escalation_tracker.record_success(task_hash, self.pro_model)
                        self.cache.set(messages, response)
                        return response
                    except Exception as e2:
                        logger.error(f"❌ Pro model also failed: {e2}")
        
        # If we reach here, Gemini failed or unavailable.
        logger.critical("🚨 LLM Unavailable - Quiet Mode Active (No Fallback)")
        return "" # Quiet Mode

# Singleton instance
router = ModelRouter()
model_router = router
