import os
from supabase import create_client, Client

# Hardcoded for debug speed (matching deploy script)
URL = "https://qwdkadwuyejyadwptgfd.supabase.co"
KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF3ZGthZHd1eWVqeWFkd3B0Z2ZkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA2MDM1MzQsImV4cCI6MjA4NjE3OTUzNH0.Lo946df4Vy_bVWjTgJtBIWo7c1PSXQw5M2r9ixCl9Q8"

supabase: Client = create_client(URL, KEY)

print("--- DEBUGGING DATA STATE ---")

# 1. Check Legacy Accounts
print("\n[1] Legacy 'public.accounts' (Source of $2000?):")
try:
    res = supabase.table("accounts").select("*").execute()
    for row in res.data:
        print(f" - Account ID: {row.get('id')}")
        print(f" - Equity: {row.get('equity')}")
        print(f" - Cash: {row.get('cash')}")
        print(f" - Updated At: {row.get('updated_at')}")
except Exception as e:
    print(f"Error fetching accounts: {e}")

# 2. Check New Crypto Snapshots
print("\n[2] New 'crypto_cash_snapshots' (Should be Real Source):")
try:
    res = supabase.table("crypto_cash_snapshots").select("*").order("taken_at", desc=True).limit(5).execute()
    if not res.data:
        print("❌ NO SNAPSHOTS FOUND! Bot failed to insert or didn't run.")
    for row in res.data:
        print(f" - Cash Available: {row.get('cash_available')}")
        print(f" - Taken At: {row.get('taken_at')}")
except Exception as e:
    print(f"Error fetching snapshots: {e}")

# 3. Check Crypto Tickers
print("\n[3] 'crypto_tickers' (Live Prices):")
try:
    res = supabase.table("crypto_tickers").select("*").execute()
    for row in res.data:
        print(f" - {row.get('symbol')}: ${row.get('price')}")
except Exception as e:
    print(f"Error fetching tickers: {e}")
