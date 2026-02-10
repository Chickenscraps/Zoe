"""
Verification script for Phase 5: Advanced Memory
"""
import os
import sys
import asyncio

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from vector_store import get_memory_store

def test_vector_store_init():
    print("\n🧪 Testing Vector Store Init...")
    store = get_memory_store()
    stats = store.get_stats()
    print(f"   Stats: {stats}")
    assert stats.get("status") in ["initialized", "keyword_fallback"]
    print("✅ Vector Store initialized.")

def test_add_and_search():
    print("\n🧪 Testing Add + Semantic Search...")
    store = get_memory_store()
    
    # Add a test memory
    success = store.add_memory(
        memory_id="test-phase5-001",
        profile_id="josh",
        content="My secret code for the vault is 8822.",
        memory_type="fact"
    )
    print(f"   Add memory: {'✅' if success else '❌'}")
    
    # Search semantically
    results = store.search("What is the vault code?", profile_id="josh", limit=3)
    print(f"   Search results: {len(results)}")
    
    found = any("8822" in r.get("content", "") for r in results)
    assert found, "Should find the secret code via semantic search"
    print("✅ Semantic search found the code!")

def test_live_ingestion_import():
    print("\n🧪 Testing Live Ingestion Function Import...")
    from memory_ingestion import ingest_recent_history
    print("✅ ingest_recent_history imported successfully.")

if __name__ == "__main__":
    test_vector_store_init()
    test_add_and_search()
    test_live_ingestion_import()
    print("\n🎉 All Phase 5 tests passed!")
