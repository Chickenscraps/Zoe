from dotenv import load_dotenv
import os
from supabase import create_client, Client

load_dotenv()
load_dotenv(".env.secrets")

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not url or not key:
    # Try alternate names if standard ones fail, or just rely on what clawdbot uses
    # clawdbot uses supabase_memory.py which likely hardcodes or reads these.
    # Let's try to import supabase_memory directly if possible, or just fail.
    print("⚠️ SUPABASE_URL or SUPABASE_KEY not found in env.")
    # Attempt to read from supabase_memory.py approach
    try:
        from supabase_memory import supabase_memory
        if supabase_memory.initialized:
            supabase = supabase_memory.client
            print("✅ Using initialized supabase_memory client.")
        else:
            print("❌ supabase_memory not initialized.")
            exit(1)
    except ImportError:
         print("❌ Could not import supabase_memory.")
         exit(1)
else:
    supabase: Client = create_client(url, key)

print("\n--- Verifying Crypto Orders (Last 5) ---")
try:
    response = supabase.table("crypto_orders").select("*").order("created_at", desc=True).limit(5).execute()
    orders = response.data
    for order in orders:
        print(f"Order {order.get('id')}: {order.get('side')} {order.get('symbol')} | Status: {order.get('status')} | Time: {order.get('created_at')}")
except Exception as e:
    print(f"Error fetching orders: {e}")

print("\n--- Verifying Crypto Fills (Existence Check) ---")
try:
    response = supabase.table("crypto_fills").select("*").limit(1).execute()
    if response.data:
        print(f"Columns found: {list(response.data[0].keys())}")
        print(f"Sample Row: {response.data[0]}")
    else:
        print("Crypto Fills table exists but is empty.")
except Exception as e:
    print(f"Error fetching fills: {e}")
