import base64
from nacl.signing import SigningKey

def generate_keys():
    # Generate random 32-byte seed
    seed = SigningKey.generate().verify_key._key
    private_key = SigningKey(seed)
    
    # Get Private Seed (Hex) - This goes in .env
    private_hex = seed.hex()
    
    # Get Public Key (Base64) - This goes to Robinhood
    public_key_bytes = private_key.verify_key.encode()
    public_b64 = base64.b64encode(public_key_bytes).decode('utf-8')
    
    print("--- KEYS GENERATED ---")
    print(f"PRIVATE_SEED_HEX: {private_hex}")
    print(f"PUBLIC_KEY_B64: {public_b64}")

if __name__ == "__main__":
    generate_keys()
