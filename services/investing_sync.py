import os
import time
import sys
import pyotp
import robin_stocks.robinhood as r
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=r"c:\Users\josha\OneDrive\Desktop\Clawd\zoe-terminal\.env") # Supabase config
load_dotenv() # Root .env for Robinhood creds

# Configuration
RH_USERNAME = os.getenv("RH_USERNAME")
RH_PASSWORD = os.getenv("RH_PASSWORD")
RH_MFA_TOTP = os.getenv("RH_MFA_TOTP") # Optional: specific TOTP secret for auto-MFA

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL")
SUPABASE_KEY = os.getenv("VITE_SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Critical: Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def login():
    if not RH_USERNAME or not RH_PASSWORD:
        print("❌ Missing RH_USERNAME or RH_PASSWORD in .env")
        return False

    try:
        if RH_MFA_TOTP:
            # Generate TOTP code if secret is provided
            totp = pyotp.TOTP(RH_MFA_TOTP).now()
            print(f"🔐 Attempting login with MFA (Code: {totp})")
            r.login(RH_USERNAME, RH_PASSWORD, mfa_code=totp)
        else:
            print("🔐 Attempting login (No MFA secret provided)...")
            r.login(RH_USERNAME, RH_PASSWORD)
        
        print("✅ Robinhood Login Successful")
        return True
    except Exception as e:
        print(f"❌ Login Failed: {e}")
        return False

def sync_loop():
    print("🚀 Starting Investing Sync Service...")
    
    if not login():
        print("⚠️  Service starting in IDLE mode due to missing credentials.")
        print("    Add RH_USERNAME, RH_PASSWORD (and optionally RH_MFA_TOTP) to .env")
        # Loop but don't crash, in case user adds them later? 
        # Actually, just exit or sleep long.
        time.sleep(10) 
        return

    while True:
        try:
            print("🔄 Fetching Profile Data...")
            
            # 1. Get Account Profile (Cash)
            profile = r.profiles.load_account_profile()
            if not profile:
                print("⚠️ Failed to load account profile")
                time.sleep(60)
                continue
                
            cash = float(profile.get("cash", 0.0))
            buying_power = float(profile.get("buying_power", 0.0))
            
            # 2. Get Portfolio Profile (Equity)
            portfolio = r.profiles.load_portfolio_profile()
            equity = float(portfolio.get("equity", 0.0)) if portfolio else 0.0
            
            print(f"💰 Cash: ${cash:.2f} | BP: ${buying_power:.2f} | Equity: ${equity:.2f}")
            
            # 3. Update Supabase
            # We assume a single user for now or get the user ID from config
            # For this simplified version, we update the first account we find or a specific one.
            # Ideally we'd look up by user.
            
            # Fetch the first account (mirrors trader logic for now)
            res = supabase.table("accounts").select("id").limit(1).execute()
            if res.data:
                account_id = res.data[0]['id']
                supabase.table("accounts").update({
                    "cash": cash,
                    "buying_power": buying_power,
                    "equity": equity,
                    "updated_at": "now()"
                }).eq("id", account_id).execute()
                print("✅ Database Updated")
            else:
                print("⚠️ No account found in DB to update")
                
        except Exception as e:
            print(f"❌ Error in sync loop: {e}")
            # Try re-login on failure?
            try:
                login()
            except:
                pass
        
        time.sleep(60) # Sync every minute

if __name__ == "__main__":
    sync_loop()
