import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT PERSONA SKILL", "memory.db")

def inspect():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- user_profile schema ---")
    cursor.execute("PRAGMA table_info(user_profile)")
    for col in cursor.fetchall():
        print(col)

    print("\n--- activity_patterns schema ---")
    cursor.execute("PRAGMA table_info(activity_patterns)")
    for col in cursor.fetchall():
        print(col)
        
    conn.close()

if __name__ == "__main__":
    inspect()
