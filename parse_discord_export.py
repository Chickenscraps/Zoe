"""
Parse Exported Discord Chat JSON
Processes Discord chat export (from DiscordChatExporter or manual export)
and organizes messages by user for persona analysis
"""
import os
import json
from collections import defaultdict
from datetime import datetime

# User IDs
USERS = {
    "292890243852664855": "Josh",
    "490911982984101901": "Ben",
    "211541044003733504": "Zac"
}

SKILL_DIR = os.path.join(os.path.dirname(__file__), "AGENT PERSONA SKILL")

def parse_discord_export(export_file):
    """
    Parse Discord chat export JSON.
    Supports DiscordChatExporter format and Discord data export format.
    """
    with open(export_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Handle different export formats
    if isinstance(data, dict):
        # DiscordChatExporter format
        messages = data.get("messages", [])
    elif isinstance(data, list):
        # Direct message list
        messages = data
    else:
        print("❌ Unknown export format")
        return []
    
    print(f"📥 Loaded {len(messages)} messages from export")
    return messages

def organize_by_user(messages):
    """
    Organize messages by user ID.
    """
    user_messages = defaultdict(list)
    
    for msg in messages:
        # Handle different author field formats
        author_id = None
        if "author" in msg:
            if isinstance(msg["author"], dict):
                author_id = msg["author"].get("id")
            else:
                author_id = msg.get("authorId")
        
        if author_id in USERS:
            user_messages[author_id].append({
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp", ""),
                "author": USERS[author_id],
                "author_id": author_id
            })
    
    return user_messages

def save_user_messages(user_messages):
    """Save messages organized by user."""
    os.makedirs(SKILL_DIR, exist_ok=True)
    
    for user_id, messages in user_messages.items():
        user_name = USERS.get(user_id, user_id)
        output_file = f"{user_name.lower()}_messages.json"
        output_path = os.path.join(SKILL_DIR, output_file)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
        
        print(f"💾 {user_name}: {len(messages)} messages → {output_file}")

def get_stats(user_messages):
    """Print statistics about the messages."""
    print("\n📊 Message Statistics:")
    total = sum(len(msgs) for msgs in user_messages.values())
    print(f"  Total messages: {total}")
    
    for user_id, messages in user_messages.items():
        user_name = USERS.get(user_id, user_id)
        percentage = (len(messages) / total * 100) if total > 0 else 0
        print(f"  {user_name}: {len(messages)} messages ({percentage:.1f}%)")

def main(export_file):
    """Main function."""
    print("🚀 Discord Chat Export Parser")
    print(f"Export file: {export_file}\n")
    
    if not os.path.exists(export_file):
        print(f"❌ File not found: {export_file}")
        print("\nPlace your Discord export JSON file in the project directory.")
        print("Supported formats:")
        print("  - DiscordChatExporter JSON")
        print("  - Discord data export")
        return
    
    # Parse export
    messages = parse_discord_export(export_file)
    
    if not messages:
        print("❌ No messages found in export")
        return
    
    # Organize by user
    user_messages = organize_by_user(messages)
    
    if not user_messages:
        print("❌ No messages from target users (Josh, Ben, Zac)")
        return
    
    # Save user-specific messages
    save_user_messages(user_messages)
    
    # Show stats
    get_stats(user_messages)
    
    print("\n✅ Complete! Ready for persona analysis.")
    print("\nNext step: Run persona analysis")
    print("  python extract_personas.py")

if __name__ == "__main__":
    import sys
    
    # Check for export file argument
    if len(sys.argv) > 1:
        export_file = sys.argv[1]
    else:
        # Look for common export file names
        possible_files = [
            "discord_export.json",
            "messages.json",
            "chat_export.json",
            "799704432929406998.json"
        ]
        
        export_file = None
        for filename in possible_files:
            if os.path.exists(filename):
                export_file = filename
                break
        
        if not export_file:
            print("❌ No export file found")
            print("\nUsage: python parse_discord_export.py <export_file.json>")
            print("\nOr place one of these files in the project directory:")
            for f in possible_files:
                print(f"  - {f}")
            exit(1)
    
    main(export_file)
