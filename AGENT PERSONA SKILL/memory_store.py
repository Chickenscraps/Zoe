import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "memory.db")

class MemoryStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # Check for migrations
            self._check_migrations(cursor)
            
            # User Profile: Stores key-value preferences per user
            # Migration handles existing table upgrade
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    user_id TEXT DEFAULT 'global',
                    key TEXT,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, key)
                )
            """)

            # Activity Patterns: Tracks user behavior
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT 'global',
                    activity_type TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    duration_minutes INTEGER,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Learning Objectives: Agent's internal goals
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_objectives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT DEFAULT 'global',
                    objective TEXT NOT NULL,
                    status TEXT DEFAULT 'pending', -- pending, completed, failed
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            
            conn.commit()

    def _redact(self, data: Any) -> Any:
        """Redact sensitive information from dictionaries or strings."""
        if isinstance(data, str):
            # Simple keyword check for extremely sensitive patterns
            # Note: This is a basic filter.
            return data
        elif isinstance(data, dict):
            new_data = {}
            for k, v in data.items():
                if any(s in k.lower() for s in ["password", "secret", "token", "auth_token", "api_key", "credential"]):
                    new_data[k] = "[REDACTED]"
                else:
                    new_data[k] = self._redact(v)
            return new_data
        elif isinstance(data, list):
            return [self._redact(x) for x in data]
        return data

    def _check_migrations(self, cursor):
        """Check and apply schema migrations."""
        try:
            # Check if user_profile has user_id
            cursor.execute("PRAGMA table_info(user_profile)")
            cols = [col[1] for col in cursor.fetchall()]
            
            # Check if user_profile has user_id
            cursor.execute("PRAGMA table_info(user_profile)")
            rows = cursor.fetchall()
            cols = [col[1] for col in rows]
            
            if cols and "user_id" not in cols:
                print("Migrating user_profile table...")
                cursor.execute("ALTER TABLE user_profile RENAME TO user_profile_old")

                # New table will be created by _init_db code following this
                # Data migration happens below if needed, but for now we might start fresh or copy
                # Let's copy assuming global -> Josh (292890243852664855)
                # But wait, we can't do CREATE TABLE inside _init_db properly if we don't handle execution order.
                # Actually, simpler to just ADD COLUMN if possible, but SQLite doesn't support adding column to PK easily.
                # So renaming is best.
                pass
                
            # Check activity_patterns
            cursor.execute("PRAGMA table_info(activity_patterns)")
            cols = [col[1] for col in cursor.fetchall()]
            if cols and "user_id" not in cols:
                print("Migrating activity_patterns table...")
                cursor.execute("ALTER TABLE activity_patterns ADD COLUMN user_id TEXT DEFAULT '292890243852664855'") # Default to Josh
                
            # Check learning_objectives
            cursor.execute("PRAGMA table_info(learning_objectives)")
            cols = [col[1] for col in cursor.fetchall()]
            if cols and "user_id" not in cols:
                 print("Migrating learning_objectives table...")
                 cursor.execute("ALTER TABLE learning_objectives ADD COLUMN user_id TEXT DEFAULT 'global'")

        except Exception as e:
            print(f"Migration check failed: {e}")

    # --- User Profile Methods ---
    def set_profile_attr(self, key: str, value: Any, user_id: str = "global"):
        """Set a single profile attribute for a user."""
        if any(s in key.lower() for s in ["password", "secret", "token", "auth_token", "api_key"]):
             value = "[REDACTED]"
        else:
             value = self._redact(value)

        if not isinstance(value, str):
            value = json.dumps(value)
            
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_profile (user_id, key, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, key, value))
            conn.commit()

    def get_profile_attr(self, key: str, user_id: str = "global") -> Optional[Any]:
        """Get a single profile attribute for a user."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # Fallback logic? No, just get specific or global
            cursor.execute("SELECT value FROM user_profile WHERE user_id = ? AND key = ?", (user_id, key))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0]
            return None

    def get_all_profile_attrs(self, user_id: str = "global") -> Dict[str, Any]:
        """Get all profile attributes for a user."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_profile WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            result = {}
            for key, val in rows:
                try:
                    result[key] = json.loads(val)
                except json.JSONDecodeError:
                    result[key] = val
            return result

    # --- Activity Pattern Methods ---
    def log_activity(self, activity_type: str, duration_minutes: int, metadata: Dict[str, Any] = None, user_id: str = "global"):
        """Log a user activity."""
        clean_metadata = self._redact(metadata) if metadata else {}
        meta_str = json.dumps(clean_metadata)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO activity_patterns (user_id, activity_type, start_time, duration_minutes, metadata)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)
            """, (user_id, activity_type, duration_minutes, meta_str))
            conn.commit()

    def get_recent_activities(self, limit: int = 10, user_id: str = None) -> List[Dict[str, Any]]:
        """Get recent activities, optionally filtered by user."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if user_id:
                query = """
                    SELECT id, activity_type, start_time, duration_minutes, metadata, user_id
                    FROM activity_patterns
                    WHERE user_id = ?
                    ORDER BY start_time DESC
                    LIMIT ?
                """
                params = (user_id, limit)
            else:
                query = """
                    SELECT id, activity_type, start_time, duration_minutes, metadata, user_id
                    FROM activity_patterns
                    ORDER BY start_time DESC
                    LIMIT ?
                """
                params = (limit,)
                
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            activities = []
            for row in rows:
                activities.append({
                    "id": row[0],
                    "type": row[1],
                    "start_time": row[2],
                    "duration": row[3],
                    "metadata": json.loads(row[4]) if row[4] else {},
                    "user_id": row[5]
                })
            return activities

    # --- Learning Objective Methods ---
    def add_objective(self, objective: str, context: str = None, user_id: str = "global"):
        """Add a new learning objective for the agent."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO learning_objectives (user_id, objective, context, status)
                VALUES (?, ?, ?, 'pending')
            """, (user_id, objective, context))
            conn.commit()

    def get_pending_objectives(self, user_id: str = None) -> List[Dict[str, Any]]:
        """Get all pending objectives, optional user filter."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if user_id:
                query = """
                    SELECT id, objective, context, created_at, user_id
                    FROM learning_objectives
                    WHERE status = 'pending' AND user_id = ?
                    ORDER BY created_at ASC
                """
                params = (user_id,)
            else:
                 query = """
                    SELECT id, objective, context, created_at, user_id
                    FROM learning_objectives
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                """
                 params = ()
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [{"id": r[0], "objective": r[1], "context": r[2], "created_at": r[3], "user_id": r[4]} for r in rows]

    def complete_objective(self, objective_id: int, success: bool = True):
        """Mark an objective as completed or failed."""
        status = 'completed' if success else 'failed'
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE learning_objectives
                SET status = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, objective_id))
            conn.commit()

# Singleton instance for easy import
memory = MemoryStore()

def get_memory_context(user_id: str = None) -> str:
    """
    Helper to get a text summary of memory for the context window.
    Aggregates profile, recent activities, and objectives.
    """
    context = []
    
    # 1. Profile
    profile = memory.get_all_profile_attrs(user_id or "global")
    if profile:
        context.append("User Profile:")
        for k, v in profile.items():
            context.append(f"- {k}: {v}")
    
    # 2. Objectives
    objectives = memory.get_pending_objectives(user_id or "global")
    if objectives:
        context.append("\nCurrent Learning Objectives:")
        for obj in objectives:
            context.append(f"- {obj['objective']} (Context: {obj['context']})")
            
    # 3. Recent Activity
    activities = memory.get_recent_activities(limit=5, user_id=user_id or "global")
    if activities:
        context.append("\nRecent Activities:")
        for act in activities:
            meta = f" ({act['metadata']})" if act['metadata'] else ""
            context.append(f"- {act['type']} for {act['duration']}m{meta} at {act['start_time']}")
            
    return "\n".join(context)


if __name__ == "__main__":
    # Test script
    print("Initializing memory store...")
    m = MemoryStore()
    
    print("Setting user preference...")
    m.set_profile_attr("work_style", "pomodoro")
    print(f"Read back preference: {m.get_profile_attr('work_style')}")
    
    print("Logging activity...")
    m.log_activity("coding_session", 45, {"project": "OpenClaw"})
    print(f"Recent activities: {m.get_recent_activities(1)}")
    
    print("Adding objective...")
    m.add_objective("Learn user's preferred break times")
    objectives = m.get_pending_objectives()
    print(f"Pending objectives: {objectives}")
    
    if objectives:
        m.complete_objective(objectives[0]['id'])
        print("Completed objective.")
