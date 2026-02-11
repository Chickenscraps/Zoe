import asyncio
import os
import yaml
from dotenv import load_dotenv
from integrations.robinhood_crypto_client import RobinhoodCryptoClient, RobinhoodCryptoConfig

# Load environment variables
load_dotenv()

async def main():
    print("--- Testing Robinhood Crypto API Balance Fetch ---")
    
    # Check keys
    api_key = os.getenv("RH_CRYPTO_API_KEY")
    seed = os.getenv("RH_CRYPTO_PRIVATE_KEY_SEED")
    
    if not api_key or not seed:
        print("❌ Missing API Keys in environment!")
        return

    print(f"API Key: {api_key[:10]}...")
    print(f"Seed: {seed[:10]}...")

    try:
        config = RobinhoodCryptoConfig.from_env()
        client = RobinhoodCryptoClient(config)
        
        print("\n⏳ Fetching account balances...")
        balances = await client.get_account_balances()
        print("\n✅ Success! Raw Access:")
        print(balances)
        
        cash = balances.get("cash_available", "N/A")
        print(f"\n💵 Cash Available: {cash}")
        
        await client.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
