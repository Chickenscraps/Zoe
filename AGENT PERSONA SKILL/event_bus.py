"""
Event Bus for Clawdbot
Central async event system for module communication.
Producers: dispatcher, proactive, news, vision, memory
Consumers: notification_router, logger, mood_engine
"""
import asyncio
import threading
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import uuid
import json

class EventType(Enum):
    # Agent wants to communicate with user
    AGENT_WANTS_USER = "agent_wants_user"
    
    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    
    # Model events
    MODEL_CALL_START = "model.call.start"
    MODEL_CALL_SUCCESS = "model.call.success"
    MODEL_CALL_FAILURE = "model.call.failure"
    
    # User interaction
    USER_MESSAGE = "user.message"
    USER_ACTION = "user.action"
    
    # News
    NEWS_PULSE = "news.pulse"
    NEWS_ERROR = "news.error"
    
    # Mood
    MOOD_CHANGE = "mood.change"
    MOOD_REVIEW = "mood.review"
    
    # Memory
    MEMORY_UPDATE = "memory.update"
    PATTERN_DETECTED = "pattern.detected"
    
    # Proactive
    PROACTIVE_NUDGE = "proactive.nudge"
    PROACTIVE_SUGGESTION = "proactive.suggestion"

class Urgency(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Event:
    """Standard event structure."""
    event_type: str
    payload: Dict[str, Any]
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "unknown"
    
    def to_dict(self) -> Dict:
        return {
            "event_type": self.event_type,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "source": self.source
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())

@dataclass
class AgentWantsUserEvent(Event):
    """
    Specialized event for when the agent wants user attention.
    Used by attention_router for notifications.
    """
    def __init__(
        self,
        title: str,
        message: str,
        urgency: Urgency = Urgency.NORMAL,
        requires_response: bool = False,
        suggested_actions: List[str] = None,
        source: str = "unknown",
        correlation_id: str = None
    ):
        payload = {
            "title": title,
            "message": message,
            "urgency": urgency.value,
            "requires_response": requires_response,
            "suggested_actions": suggested_actions or ["Open UI", "Reply", "Snooze 15m"]
        }
        super().__init__(
            event_type=EventType.AGENT_WANTS_USER.value,
            payload=payload,
            correlation_id=correlation_id or str(uuid.uuid4()),
            source=source
        )

class EventBus:
    """
    Simple in-process event bus with async support.
    Thread-safe for use across sync and async contexts.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._subscribers: Dict[str, List[Callable]] = {}
        self._async_subscribers: Dict[str, List[Callable]] = {}
        self._event_queue: asyncio.Queue = None
        self._history: List[Event] = []
        self._max_history = 100
        self._lock = threading.Lock()
        self._initialized = True
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe a sync callback to an event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
    
    def subscribe_async(self, event_type: str, callback: Callable):
        """Subscribe an async callback to an event type."""
        with self._lock:
            if event_type not in self._async_subscribers:
                self._async_subscribers[event_type] = []
            self._async_subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe a callback from an event type."""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    cb for cb in self._subscribers[event_type] if cb != callback
                ]
            if event_type in self._async_subscribers:
                self._async_subscribers[event_type] = [
                    cb for cb in self._async_subscribers[event_type] if cb != callback
                ]
    
    def publish(self, event: Event):
        """
        Publish an event to all subscribers.
        Sync callbacks are called immediately.
        Async callbacks are scheduled.
        """
        # Store in history
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        
        # Call sync subscribers
        event_type = event.event_type
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"[EventBus] Sync subscriber error for {event_type}: {e}")
        
        # Wildcard subscribers (listen to all events)
        if "*" in self._subscribers:
            for callback in self._subscribers["*"]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"[EventBus] Wildcard subscriber error: {e}")
        
        # Handle async subscribers
        if event_type in self._async_subscribers or "*" in self._async_subscribers:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._dispatch_async(event))
                else:
                    loop.run_until_complete(self._dispatch_async(event))
            except RuntimeError:
                # No event loop, skip async subscribers
                pass
    
    async def _dispatch_async(self, event: Event):
        """Dispatch event to async subscribers."""
        event_type = event.event_type
        
        callbacks = []
        if event_type in self._async_subscribers:
            callbacks.extend(self._async_subscribers[event_type])
        if "*" in self._async_subscribers:
            callbacks.extend(self._async_subscribers["*"])
        
        for callback in callbacks:
            try:
                await callback(event)
            except Exception as e:
                print(f"[EventBus] Async subscriber error for {event_type}: {e}")
    
    def publish_agent_wants_user(
        self,
        title: str,
        message: str,
        urgency: Urgency = Urgency.NORMAL,
        requires_response: bool = False,
        suggested_actions: List[str] = None,
        source: str = "unknown"
    ):
        """Convenience method for agent_wants_user events."""
        event = AgentWantsUserEvent(
            title=title,
            message=message,
            urgency=urgency,
            requires_response=requires_response,
            suggested_actions=suggested_actions,
            source=source
        )
        self.publish(event)
        return event.correlation_id
    
    def get_recent_events(self, count: int = 10, event_type: str = None) -> List[Event]:
        """Get recent events from history."""
        with self._lock:
            if event_type:
                filtered = [e for e in self._history if e.event_type == event_type]
                return filtered[-count:]
            return self._history[-count:]

# Global singleton instance
event_bus = EventBus()

# Convenience functions
def publish(event: Event):
    """Publish an event to the global bus."""
    event_bus.publish(event)

def subscribe(event_type: str, callback: Callable):
    """Subscribe to events on the global bus."""
    event_bus.subscribe(event_type, callback)

def notify_user(title: str, message: str, urgency: str = "normal", source: str = "unknown"):
    """Convenience function to emit agent_wants_user event."""
    urgency_enum = Urgency(urgency) if urgency in [u.value for u in Urgency] else Urgency.NORMAL
    return event_bus.publish_agent_wants_user(
        title=title,
        message=message,
        urgency=urgency_enum,
        source=source
    )

if __name__ == "__main__":
    # Test
    def test_handler(event: Event):
        print(f"Received: {event.event_type} - {event.payload}")
    
    subscribe(EventType.AGENT_WANTS_USER.value, test_handler)
    subscribe("*", lambda e: print(f"[Wildcard] {e.event_type}"))
    
    cid = notify_user("Test Title", "Test message!", urgency="high", source="test")
    print(f"Published with correlation_id: {cid}")
    
    print(f"Recent events: {len(event_bus.get_recent_events())}")
