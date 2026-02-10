"""
Discord Message Fetcher v2 - Using OpenClaw Gateway
Fetches messages using the OpenClaw Discord integration
"""
import os
import json
import subprocess
from collections import defaultdict

# User IDs
USERS = {
    "292890243852664855": "Josh",
    "490911982984101901": "Ben",
    "211541044003733504": "Zac"
}

CHANNEL_ID = "799704432929406998"
PROJECT_ROOT = os.path.dirname(__file__)

def fetch_messages_via_gateway(channel_id, limit=100, before=None):
    """
    Fetch messages using OpenClaw gateway.
    This uses the gateway's Discord integration which should have proper permissions.
    """
    # Build the command
    params = {
        "channelId": channel_id,
        "limit": limit
    }
    if before:
        params["before"] = before
    
    # Use the gateway's Discord readMessages action
    import requests
    
    gateway_url = "http://localhost:18789"
    
    try:
        # Call the gateway API directly
        response = requests.post(
            f"{gateway_url}/api/discord/readMessages",
            json=params,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("messages", [])
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return []
    except Exception as e:
        print(f"Error fetching via gateway: {e}")
        return []

def fetch_all_messages_paginated(channel_id, max_messages=None):
    """
    Fetch all messages with pagination.
    """
    all_messages = []
    before = None
    batch_count = 0
    
    print(f"📥 Fetching messages from channel {channel_id} via OpenClaw gateway...")
    
    while True:
        batch_count += 1
        print(f"  Batch {batch_count}: Fetching up to 100 messages...")
        
        messages = fetch_messages_via_gateway(channel_id, limit=100, before=before)
        
        if not messages:
            print("  No more messages to fetch.")
            break
        
        all_messages.extend(messages)
        print(f"  Fetched {len(messages)} messages (Total: {len(all_messages)})")
        
        # Check if we've hit the limit
        if max_messages and len(all_messages) >= max_messages:
            print(f"  Reached max_messages limit ({max_messages})")
            all_messages = all_messages[:max_messages]
            break
        
        # Get the oldest message ID for next batch
        before = messages[-1].get("id")
        
        if not before:
            print("  No message ID found, stopping.")
            break
    
    print(f"\n✅ Fetched {len(all_messages)} total messages")
    return all_messages

def organize_by_user(messages):
    """
    Organize messages by user ID.
    """
    user_messages = defaultdict(list)
    
    for msg in messages:
        author_id = msg.get("author", {}).get("id")
        if author_id in USERS:
            user_messages[author_id].append(msg)
    
    return user_messages

def save_messages(messages, output_file="discord_chat_history.json"):
    """Save all messages to JSON file."""
    output_path = os.path.join(PROJECT_ROOT, output_file)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
    
    print(f"💾 All messages saved to {output_path}")
    return output_path

def save_user_messages(user_messages):
    """Save messages organized by user."""
    for user_id, messages in user_messages.items():
        user_name = USERS.get(user_id, user_id)
        output_file = f"{user_name.lower()}_messages.json"
        output_path = os.path.join(PROJECT_ROOT, "AGENT PERSONA SKILL", output_file)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
        
        print(f"💾 {user_name}'s messages saved to {output_path} ({len(messages)} messages)")

def get_stats(user_messages):
    """Print statistics about the messages."""
    print("\n📊 Message Statistics:")
    for user_id, messages in user_messages.items():
        user_name = USERS.get(user_id, user_id)
        print(f"  {user_name}: {len(messages)} messages")

def main():
    """Main function."""
    print("🚀 Discord Message Fetcher v2 (OpenClaw Gateway)")
    print(f"Channel: {CHANNEL_ID}")
    print(f"Target users: {', '.join(USERS.values())}\n")
    
    # Fetch messages (start with 1000 for testing, then increase)
    messages = fetch_all_messages_paginated(CHANNEL_ID, max_messages=1000)
    
    if not messages:
        print("\n❌ No messages fetched. Possible issues:")
        print("  1. Gateway not running (check http://localhost:18789)")
        print("  2. Bot doesn't have access to channel 799704432929406998")
        print("  3. Channel ID is incorrect")
        return
    
    # Save all messages
    save_messages(messages)
    
    # Organize by user
    user_messages = organize_by_user(messages)
    
    # Save user-specific messages
    save_user_messages(user_messages)
    
    # Show stats
    get_stats(user_messages)
    
    print("\n✅ Complete!")

if __name__ == "__main__":
    # Check if requests is installed
    try:
        import requests
    except ImportError:
        print("❌ 'requests' library not installed.")
        print("Run: pip install requests")
        exit(1)
    
    main()
