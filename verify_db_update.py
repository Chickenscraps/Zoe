import os
import sys
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv

# Load from zoe-terminal .env where we just wrote the new keys
load_dotenv(dotenv_path=r"c:\Users\josha\OneDrive\Desktop\Clawd\zoe-terminal\.env")

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL")
SUPABASE_KEY = os.getenv("VITE_SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing Supabase Creds in env file")
    sys.exit(1)

print(f"Connecting to: {SUPABASE_URL}")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_and_seed():
    print("------- Checking DB Account Balances -------")
    try:
        # 1. Check if ANY account exists
        res = supabase.table("accounts").select("*").limit(1).execute()
        
        if res.data:
            acc = res.data[0]
            print(f"✅ Account Found: {acc.get('id')}")
            print(f"   Equity:       ${acc.get('equity')}")
            print(f"   Cash:         ${acc.get('cash')}")
            print(f"   Buying Power: ${acc.get('buying_power')}")
            
            if float(acc.get('cash', 0)) == 2000.0:
                print("\n⚠️  Balance is default $2000.00. Sync service needs to run.")
            else:
                print("\n✅ Balance differs from default! Sync might be working.")
        else:
            print("❌ No account found. Attempting to SEED data...")
            seed_data()
            
    except Exception as e:
        print(f"❌ Error connecting/reading: {e}")

def seed_data():
    try:
        # Create user if not exists
        discord_id = "292890243852664855" # Default from seed_v4.sql
        print(f"   Creating User ({discord_id})...")
        
        # Upsert User
        user_data = {"discord_id": discord_id, "username": "Chickenscraps"}
        user_res = supabase.table("users").upsert(user_data, on_conflict="discord_id").execute()
        
        # Get User ID
        if user_res.data:
            user_id = user_res.data[0]['id']
        else:
            # Try fetch if upsert didn't return (shouldn't happen with default headers but safe check)
            u_res = supabase.table("users").select("id").eq("discord_id", discord_id).single().execute()
            user_id = u_res.data['id']
            
        print(f"   User ID: {user_id}")
        
        # Create Account
        print("   Creating Default Account...")
        acc_data = {
            "user_id": user_id,
            "instance_id": "default",
            "equity": 2000.00,
            "cash": 2000.00,
            "buying_power": 2000.00
        }
        supabase.table("accounts").insert(acc_data).execute()
        print("✅ Seed Complete! Re-run verify to check.")
        
    except Exception as e:
        print(f"❌ Seeding Failed: {e}")

if __name__ == "__main__":
    check_and_seed()
