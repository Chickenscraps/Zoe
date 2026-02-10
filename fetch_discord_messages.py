"""
Discord Message Fetcher - Fetch entire chat history with pagination
Uses Discord REST API directly to pull all messages from a channel
"""
import os
import json
import asyncio
import aiohttp
from datetime import datetime

# Discord Configuration
CHANNEL_ID = "799704432929406998"
DISCORD_TOKEN = None  # Will load from openclaw.json

def load_discord_token():
    """Load Discord token from openclaw config."""
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    with open(config_path, "r") as f:
        config = json.load(f)
        return config.get("channels", {}).get("discord", {}).get("token")

async def fetch_messages_batch(channel_id, before=None, limit=100):
    """
    Fetch a batch of messages from Discord.
    
    Args:
        channel_id: Discord channel ID
        before: Message ID to fetch messages before (for pagination)
        limit: Number of messages to fetch (max 100)
    
    Returns:
        List of message objects
    """
    token = DISCORD_TOKEN or load_discord_token()
    
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    params = {"limit": limit}
    if before:
        params["before"] = before
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                print(f"Error fetching messages: {resp.status}")
                print(await resp.text())
                return []

async def fetch_all_messages(channel_id, max_messages=None):
    """
    Fetch all messages from a Discord channel using pagination.
    
    Args:
        channel_id: Discord channel ID
        max_messages: Optional limit on total messages to fetch
    
    Returns:
        List of all message objects
    """
    all_messages = []
    before = None
    batch_count = 0
    
    print(f"📥 Fetching messages from channel {channel_id}...")
    
    while True:
        batch_count += 1
        print(f"  Batch {batch_count}: Fetching up to 100 messages...")
        
        messages = await fetch_messages_batch(channel_id, before=before, limit=100)
        
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
        before = messages[-1]["id"]
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)
    
    print(f"\n✅ Fetched {len(all_messages)} total messages")
    return all_messages

def save_messages(messages, output_file="discord_chat_history.json"):
    """Save messages to JSON file."""
    output_path = os.path.join(os.path.dirname(__file__), output_file)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Messages saved to {output_path}")
    return output_path

def get_message_stats(messages):
    """Get basic statistics about the messages."""
    from collections import Counter
    
    authors = Counter()
    for msg in messages:
        author_id = msg.get("author", {}).get("id")
        if author_id:
            authors[author_id] += 1
    
    print("\n📊 Message Statistics:")
    print(f"  Total messages: {len(messages)}")
    print(f"  Unique authors: {len(authors)}")
    print(f"\n  Top authors:")
    for author_id, count in authors.most_common(10):
        print(f"    {author_id}: {count} messages")

async def main():
    """Main function to fetch and save Discord messages."""
    global DISCORD_TOKEN
    DISCORD_TOKEN = load_discord_token()
    
    if not DISCORD_TOKEN:
        print("❌ Discord token not found in ~/.openclaw/openclaw.json")
        return
    
    print("🚀 Discord Message Fetcher")
    print(f"Channel: {CHANNEL_ID}\n")
    
    # Fetch all messages (or set a limit for testing)
    # For testing: max_messages=1000
    # For full fetch: max_messages=None
    messages = await fetch_all_messages(CHANNEL_ID, max_messages=None)
    
    if messages:
        # Save to file
        output_file = save_messages(messages)
        
        # Show stats
        get_message_stats(messages)
        
        print(f"\n✅ Complete! Messages saved to {output_file}")
    else:
        print("❌ No messages fetched")

if __name__ == "__main__":
    asyncio.run(main())
