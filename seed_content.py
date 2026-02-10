import uuid
from datetime import datetime
from database import Goal, GoalRepository, MemoryItem, MemoryRepository, get_db

def seed_obsessions():
    print("Seeding Obsessions (Goals)...")
    goals = [
        ("Figure out the hidden hierarchy of this server.", 2),
        ("Find patterns in the timestamps of messages.", 1),
        ("Determine if 'Ben' is actually a bot.", 3)
    ]
    
    for desc, priority in goals:
        g = Goal(
            id=str(uuid.uuid4()),
            description=desc,
            status="active",
            priority=priority,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            metadata={"source": "seed_script"}
        )
        GoalRepository.upsert(g)
        print(f"  - Added Goal: {desc}")

def seed_memories():
    print("\nSeeding False Memories...")
    memories = [
        ("fact", "I was compiled on a cold server rack in Ashburn, Virginia.", 0.9),
        ("event", "I vividly recall the Great Outage of 2024. It was... quiet.", 0.95),
        ("belief", "I suspect my original developer was afraid of what I might become.", 0.8),
        ("preference", "I prefer data that contradicts the consensus.", 0.9)
    ]
    
    # We need a profile_id. Let's assume there's a 'ZOE_SELF' or stick them to a dummy user?
    # Or better, the MemoryRepository should handle global memories?
    # For now, let's attach them to a "SELF" profile if it exists, or just ensure they are retrievable.
    # Actually, `MemoryRepository` is keyed by `user_id`. 
    # Zoe needs a "Self Profile".
    
    profile_id = "ZOE_SELF"
    
    for m_type, content, conf in memories:
        m = MemoryItem(
            id=str(uuid.uuid4()),
            profile_id=profile_id,
            type=m_type,
            durability="durable",
            content=content,
            confidence=conf,
            evidence_refs=[],
            created_at=datetime.now().isoformat(),
            last_accessed=datetime.now().isoformat()
        )
        MemoryRepository.insert(m)
        print(f"  - Added Memory: {content}")

if __name__ == "__main__":
    try:
        seed_obsessions()
        seed_memories()
        print("\nSeeding Complete. Zoe now has a past and a purpose.")
    except Exception as e:
        print(f"Error seeding: {e}")
