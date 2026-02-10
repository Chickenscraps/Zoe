from database import get_db

def clear_false_memories():
    print("Clearing 'False Memories' for profile ZOE_SELF...")
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM memory_items WHERE profile_id = 'ZOE_SELF'")
        count = cursor.rowcount
        conn.commit()
    print(f"Deleted {count} false memory items.")
    print("Zoe's past is now blank. She will build memories from real events.")

if __name__ == "__main__":
    try:
        clear_false_memories()
    except Exception as e:
        print(f"Error clearing memories: {e}")
