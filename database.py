"""
Database Models & Schema for AGI-Lite Clawdbot
SQLite for structured data (profiles, moods, audit logs)
"""
import os
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

# ============================================================================
# Configuration
# ============================================================================

DB_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "clawdbot.db"

# ============================================================================
# Schema Definitions
# ============================================================================

SCHEMA_SQL = """
-- User Profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id TEXT PRIMARY KEY,
    discord_ids TEXT NOT NULL,  -- JSON array
    aliases TEXT NOT NULL,  -- JSON array
    communication_style TEXT NOT NULL,  -- JSON object
    boundaries TEXT NOT NULL,  -- JSON object
    interests TEXT NOT NULL,  -- JSON object
    motivation_levers TEXT NOT NULL,  -- JSON object
    interaction_rules TEXT NOT NULL,  -- JSON object
    fingerprint TEXT NOT NULL,  -- JSON object
    last_updated TEXT NOT NULL,
    evidence_refs TEXT NOT NULL  -- JSON array
);

-- Mood Logs
CREATE TABLE IF NOT EXISTS mood_logs (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,  -- text, voice, video
    signals TEXT NOT NULL,  -- JSON object
    trigger_message_id TEXT,
    sensor_data TEXT,  -- JSON object
    FOREIGN KEY (profile_id) REFERENCES user_profiles(profile_id)
);

-- Memory Items
CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    type TEXT NOT NULL,  -- fact, preference, event, relationship, boundary
    durability TEXT NOT NULL,  -- durable, ephemeral
    content TEXT NOT NULL,
    embedding TEXT,  -- JSON array of floats
    confidence REAL NOT NULL,
    evidence_refs TEXT NOT NULL,  -- JSON array
    created_at TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    access_count INTEGER DEFAULT 1,
    superseded_by TEXT,
    expires_at TEXT,
    FOREIGN KEY (profile_id) REFERENCES user_profiles(profile_id)
);

-- Message Events (for imported history & runtime)
CREATE TABLE IF NOT EXISTS message_events (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,  -- discord, imported_json
    discord_message_id TEXT,
    channel_id TEXT NOT NULL,
    guild_id TEXT,
    user_id TEXT NOT NULL,
    profile_id TEXT,
    content TEXT NOT NULL,
    attachments TEXT,  -- JSON array
    reactions TEXT,  -- JSON array
    reply_to_id TEXT,
    timestamp TEXT NOT NULL,
    inferred_mood TEXT,  -- JSON object
    fingerprint TEXT,  -- JSON object
    FOREIGN KEY (profile_id) REFERENCES user_profiles(profile_id)
);

-- Daily Digests
CREATE TABLE IF NOT EXISTS daily_digests (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    group_summary TEXT NOT NULL,  -- JSON object
    individual_checkins TEXT NOT NULL,  -- JSON object
    metrics TEXT  -- JSON object
);

-- Tool Audit Log
CREATE TABLE IF NOT EXISTS tool_audit_events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    tool TEXT NOT NULL,
    args TEXT NOT NULL,  -- JSON object
    reason TEXT NOT NULL,
    trigger_type TEXT,
    trigger_message_id TEXT,
    result TEXT NOT NULL,  -- JSON object
    confirmation_required INTEGER DEFAULT 0,
    confirmed_by TEXT
);

-- Privacy State
CREATE TABLE IF NOT EXISTS privacy_state (
    guild_id TEXT PRIMARY KEY,
    user_overrides TEXT NOT NULL,  -- JSON object
    global_defaults TEXT NOT NULL,  -- JSON object
    last_sensor_activity TEXT  -- JSON object
);

-- Task Plans (Multi-turn planning)
CREATE TABLE IF NOT EXISTS task_plans (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,  -- planning, executing, completed, failed, cancelled
    created_at TEXT NOT NULL,
    completed_at TEXT,
    final_result TEXT,
    user_id TEXT
);

-- Task Steps (Individual steps in a plan)
CREATE TABLE IF NOT EXISTS task_steps (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    description TEXT NOT NULL,
    tool TEXT NOT NULL,
    args TEXT NOT NULL,  -- JSON object
    status TEXT NOT NULL,  -- pending, running, completed, failed, skipped
    result TEXT,
    error TEXT,
    depends_on TEXT,  -- JSON array of step IDs
    FOREIGN KEY (plan_id) REFERENCES task_plans(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_mood_profile ON mood_logs(profile_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_memory_profile ON memory_items(profile_id, type);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON message_events(channel_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_user ON message_events(user_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_tool ON tool_audit_events(tool, timestamp);

-- Goals (Active Obsessions)
CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    status TEXT NOT NULL, -- active, completed, dropped
    priority INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT -- JSON object for context
);
"""

# ============================================================================
# Database Connection
# ============================================================================

@contextmanager
def get_db():
    """Get database connection with proper cleanup."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize database with schema."""
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    print(f"✅ Database initialized at {DB_PATH}")

# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class UserProfile:
    profile_id: str
    discord_ids: List[str]
    aliases: List[str]
    communication_style: Dict[str, Any]
    boundaries: Dict[str, Any]
    interests: Dict[str, Any]
    motivation_levers: Dict[str, Any]
    interaction_rules: Dict[str, Any]
    fingerprint: Dict[str, Any]
    last_updated: str
    evidence_refs: List[str]

@dataclass
class MoodLog:
    id: str
    profile_id: str
    timestamp: str
    source: str
    signals: Dict[str, Any]
    trigger_message_id: Optional[str] = None
    sensor_data: Optional[Dict[str, Any]] = None

@dataclass
class MessageEvent:
    id: str
    source: str
    channel_id: str
    user_id: str
    content: str
    timestamp: str
    profile_id: Optional[str] = None
    discord_message_id: Optional[str] = None
    guild_id: Optional[str] = None
    attachments: Optional[List[str]] = None
    reply_to_id: Optional[str] = None
    inferred_mood: Optional[Dict[str, Any]] = None

@dataclass
class MemoryItem:
    id: str
    profile_id: str
    type: str
    durability: str
    content: str
    confidence: float
    evidence_refs: List[Dict[str, str]]
    created_at: str
    last_accessed: str
    access_count: int = 1
    embedding: Optional[List[float]] = None
    superseded_by: Optional[str] = None
    expires_at: Optional[str] = None

# ============================================================================
# CRUD Operations
# ============================================================================

class ProfileRepository:
    """CRUD for user profiles."""
    
    @staticmethod
    def upsert(profile: UserProfile):
        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_profiles 
                (profile_id, discord_ids, aliases, communication_style, boundaries,
                 interests, motivation_levers, interaction_rules, fingerprint,
                 last_updated, evidence_refs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.profile_id,
                json.dumps(profile.discord_ids),
                json.dumps(profile.aliases),
                json.dumps(profile.communication_style),
                json.dumps(profile.boundaries),
                json.dumps(profile.interests),
                json.dumps(profile.motivation_levers),
                json.dumps(profile.interaction_rules),
                json.dumps(profile.fingerprint),
                profile.last_updated,
                json.dumps(profile.evidence_refs)
            ))
            conn.commit()
    
    @staticmethod
    def get(profile_id: str) -> Optional[UserProfile]:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM user_profiles WHERE profile_id = ?",
                (profile_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return UserProfile(
                profile_id=row["profile_id"],
                discord_ids=json.loads(row["discord_ids"]),
                aliases=json.loads(row["aliases"]),
                communication_style=json.loads(row["communication_style"]),
                boundaries=json.loads(row["boundaries"]),
                interests=json.loads(row["interests"]),
                motivation_levers=json.loads(row["motivation_levers"]),
                interaction_rules=json.loads(row["interaction_rules"]),
                fingerprint=json.loads(row["fingerprint"]),
                last_updated=row["last_updated"],
                evidence_refs=json.loads(row["evidence_refs"])
            )
    
    @staticmethod
    def get_by_discord_id(discord_id: str) -> Optional[UserProfile]:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM user_profiles").fetchall()
            for row in rows:
                discord_ids = json.loads(row["discord_ids"])
                if discord_id in discord_ids:
                    return ProfileRepository.get(row["profile_id"])
        return None
    
    @staticmethod
    def get_all() -> List[UserProfile]:
        with get_db() as conn:
            rows = conn.execute("SELECT profile_id FROM user_profiles").fetchall()
            return [ProfileRepository.get(row["profile_id"]) for row in rows]


class MoodRepository:
    """CRUD for mood logs."""
    
    @staticmethod
    def insert(mood: MoodLog):
        with get_db() as conn:
            conn.execute("""
                INSERT INTO mood_logs 
                (id, profile_id, timestamp, source, signals, trigger_message_id, sensor_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                mood.id,
                mood.profile_id,
                mood.timestamp,
                mood.source,
                json.dumps(mood.signals),
                mood.trigger_message_id,
                json.dumps(mood.sensor_data) if mood.sensor_data else None
            ))
            conn.commit()

    @staticmethod
    def log_interaction(profile_id: str, source: str, content: str):
        """Helper to log a simple interaction as a mood signal."""
        # Mock signals for now
        signals = {"tone": "neutral", "intensity": 0.5}
        
        mood = MoodLog(
            id=str(uuid.uuid4()),
            profile_id=profile_id,
            timestamp=datetime.now().isoformat(),
            source=source,
            signals=signals,
            trigger_message_id=None,
            sensor_data={"content_summary": content[:50]}
        )
        MoodRepository.insert(mood)
    
    @staticmethod
    def get_recent(profile_id: str, hours: int = 24) -> List[MoodLog]:
        with get_db() as conn:
            # Simple implementation - in production use proper datetime comparison
            rows = conn.execute("""
                SELECT * FROM mood_logs 
                WHERE profile_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 50
            """, (profile_id,)).fetchall()
            
            return [MoodLog(
                id=row["id"],
                profile_id=row["profile_id"],
                timestamp=row["timestamp"],
                source=row["source"],
                signals=json.loads(row["signals"]),
                trigger_message_id=row["trigger_message_id"],
                sensor_data=json.loads(row["sensor_data"]) if row["sensor_data"] else None
            ) for row in rows]
    
    @staticmethod
    def get_trend(profile_id: str, hours: int = 24) -> Dict[str, Any]:
        """Calculate mood trend for a user."""
        moods = MoodRepository.get_recent(profile_id, hours)
        
        if not moods:
            return {"trend": "unknown", "avg_intensity": 0.5, "dominant_tone": "neutral"}
        
        tones = [m.signals.get("tone", "neutral") for m in moods]
        intensities = [m.signals.get("intensity", 0.5) for m in moods]
        
        # Simple trend calculation
        tone_counts = {}
        for t in tones:
            tone_counts[t] = tone_counts.get(t, 0) + 1
        
        dominant = max(tone_counts, key=tone_counts.get) if tone_counts else "neutral"
        avg_intensity = sum(intensities) / len(intensities) if intensities else 0.5
        
        return {
            "trend": "positive" if dominant in ["excited", "playful", "happy"] else 
                     "negative" if dominant in ["stressed", "frustrated", "tired"] else "neutral",
            "avg_intensity": round(avg_intensity, 2),
            "dominant_tone": dominant,
            "sample_count": len(moods)
        }

    @staticmethod
    def delete_all(profile_id: str):
        """Delete all mood logs for a user (Privacy Request)."""
        with get_db() as conn:
            conn.execute("DELETE FROM mood_logs WHERE profile_id = ?", (profile_id,))
            conn.commit()


class MemoryRepository:
    """CRUD for memory items."""
    
    @staticmethod
    def insert(memory: MemoryItem):
        with get_db() as conn:
            conn.execute("""
                INSERT INTO memory_items 
                (id, profile_id, type, durability, content, embedding, confidence,
                 evidence_refs, created_at, last_accessed, access_count, superseded_by, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.id,
                memory.profile_id,
                memory.type,
                memory.durability,
                memory.content,
                json.dumps(memory.embedding) if memory.embedding else None,
                memory.confidence,
                json.dumps(memory.evidence_refs),
                memory.created_at,
                memory.last_accessed,
                memory.access_count,
                memory.superseded_by,
                memory.expires_at
            ))
            conn.commit()
    
    @staticmethod
    def get_by_profile(profile_id: str, limit: int = 50) -> List[MemoryItem]:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT * FROM memory_items 
                WHERE profile_id = ? AND superseded_by IS NULL
                ORDER BY access_count DESC, last_accessed DESC
                LIMIT ?
            """, (profile_id, limit)).fetchall()
            
            return [MemoryItem(
                id=row["id"],
                profile_id=row["profile_id"],
                type=row["type"],
                durability=row["durability"],
                content=row["content"],
                embedding=json.loads(row["embedding"]) if row["embedding"] else None,
                confidence=row["confidence"],
                evidence_refs=json.loads(row["evidence_refs"]),
                created_at=row["created_at"],
                last_accessed=row["last_accessed"],
                access_count=row["access_count"],
                superseded_by=row["superseded_by"],
                expires_at=row["expires_at"]
            ) for row in rows]
    
    @staticmethod
    def touch(memory_id: str):
        """Update access time and count."""
        with get_db() as conn:
            conn.execute("""
                UPDATE memory_items 
                SET last_accessed = ?, access_count = access_count + 1
                WHERE id = ?
            """, (datetime.now().isoformat(), memory_id))
            conn.commit()

    @staticmethod
    def delete_all(profile_id: str):
        """Delete all memory items for a user (Privacy Request)."""
        with get_db() as conn:
            conn.execute("DELETE FROM memory_items WHERE profile_id = ?", (profile_id,))
            conn.commit()


class MessageRepository:
    """CRUD for message events (Chat History)."""
    
    @staticmethod
    def insert(msg: MessageEvent):
        with get_db() as conn:
            conn.execute("""
                INSERT INTO message_events 
                (id, source, discord_message_id, channel_id, guild_id, user_id, profile_id,
                 content, attachments, timestamp, reply_to_id, inferred_mood)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                msg.id,
                msg.source,
                msg.discord_message_id,
                msg.channel_id,
                msg.guild_id,
                msg.user_id,
                msg.profile_id,
                msg.content,
                json.dumps(msg.attachments) if msg.attachments else None,
                msg.timestamp,
                msg.reply_to_id,
                json.dumps(msg.inferred_mood) if msg.inferred_mood else None
            ))
            conn.commit()

    @staticmethod
    def get_recent(channel_id: str, limit: int = 20) -> List[MessageEvent]:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT * FROM message_events 
                WHERE channel_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (channel_id, limit)).fetchall()
            
            # Return reversed (chronological)
            events = []
            for row in rows:
                events.append(MessageEvent(
                    id=row["id"],
                    source=row["source"],
                    channel_id=row["channel_id"],
                    user_id=row["user_id"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    profile_id=row["profile_id"],
                    discord_message_id=row["discord_message_id"],
                    guild_id=row["guild_id"],
                    attachments=json.loads(row["attachments"]) if row["attachments"] else None,
                    reply_to_id=row["reply_to_id"],
                    inferred_mood=json.loads(row["inferred_mood"]) if row["inferred_mood"] else None
                ))
            return list(reversed(events))

    @staticmethod
    def get_stats_now(hours: int = 24) -> Dict[str, Any]:
        """Get quick stats for last N hours."""
        # TODO: Implement actual time filtering
        # For now just count all in DB as a stub or implement real SQL
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM message_events").fetchone()[0]
        return {"count": count}


@dataclass
class Goal:
    id: str
    description: str
    status: str
    created_at: str
    updated_at: str
    priority: int = 1
    metadata: Optional[Dict[str, Any]] = None

class GoalRepository:
    """CRUD for Goals (Obsessions)."""
    
    @staticmethod
    def upsert(goal: Goal):
        with get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO goals 
                (id, description, status, priority, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                goal.id,
                goal.description,
                goal.status,
                goal.priority,
                goal.created_at,
                goal.updated_at,
                json.dumps(goal.metadata) if goal.metadata else None
            ))
            conn.commit()
            
    @staticmethod
    def get_active() -> List[Goal]:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM goals WHERE status = 'active' ORDER BY priority DESC").fetchall()
            return [Goal(
                id=row["id"],
                description=row["description"],
                status=row["status"],
                priority=row["priority"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None
            ) for row in rows]



# ============================================================================
# Migration: Import existing persona data
# ============================================================================

def migrate_from_persona_json():
    """Import existing user_personas.json into SQLite."""
    persona_file = Path(os.path.dirname(os.path.abspath(__file__))) / "AGENT PERSONA SKILL" / "user_personas.json"
    
    if not persona_file.exists():
        print(f"⚠️ No persona file found at {persona_file}")
        return
    
    with open(persona_file, "r", encoding="utf-8") as f:
        personas = json.load(f)
    
    discord_id_map = {
        "Josh": "292890243852664855",
        "Ben": "490911982984101901",
        "Zac": "211541044003733504"
    }
    
    for name, data in personas.items():
        profile = UserProfile(
            profile_id=name.lower(),
            discord_ids=[data.get("user_id", discord_id_map.get(name, ""))],
            aliases=[name],
            communication_style={
                "verbosity": "medium",
                "slang_level": "high",
                "humor_type": data.get("humor_type", []),
                "style": data.get("communication_style", "casual")
            },
            boundaries={
                "sensitive_topics": [],
                "dont_joke_about": [],
                "preferred_support_style": "tease"
            },
            interests={
                "primary": data.get("interests", []),
                "inside_jokes": data.get("inside_jokes", [])
            },
            motivation_levers={
                "what_gets_them_moving": [],
                "what_shuts_them_down": []
            },
            interaction_rules={
                "do": data.get("common_phrases", []),
                "dont": []
            },
            fingerprint={
                "common_phrases": data.get("common_phrases", []),
                "response_patterns": data.get("response_patterns", {})
            },
            last_updated=data.get("last_updated", datetime.now().isoformat()),
            evidence_refs=[]
        )
        
        ProfileRepository.upsert(profile)
        print(f"✅ Migrated profile: {name}")
    
    print(f"✅ Migration complete - {len(personas)} profiles imported")


# ============================================================================
# Initialize
# ============================================================================

if __name__ == "__main__":
    init_db()
    migrate_from_persona_json()
    
    # Test retrieval
    profiles = ProfileRepository.get_all()
    print(f"\n📊 Database has {len(profiles)} profiles")
    for p in profiles:
        print(f"   - {p.profile_id}: {p.aliases}")
