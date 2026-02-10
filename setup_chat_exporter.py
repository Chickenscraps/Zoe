import os
import zipfile
import urllib.request

# Use specific version URL for Windows x64
DOWNLOAD_URL = "https://github.com/Tyrrrz/DiscordChatExporter/releases/download/2.46/DiscordChatExporter.Cli.win-x64.zip"
ZIP_FILE = "DiscordChatExporter.zip"
EXTRACT_DIR = "DiscordChatExporter"

def download_chat_exporter():
    """Download DiscordChatExporter from GitHub."""
    print("📥 Downloading DiscordChatExporter...")
    print(f"URL: {DOWNLOAD_URL}")
    
    try:
        urllib.request.urlretrieve(DOWNLOAD_URL, ZIP_FILE)
        print(f"✅ Downloaded to {ZIP_FILE}")
        return True
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False

def extract_zip():
    """Extract the downloaded ZIP file."""
    print(f"\n📦 Extracting {ZIP_FILE}...")
    
    try:
        os.makedirs(EXTRACT_DIR, exist_ok=True)
        
        with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)
        
        print(f"✅ Extracted to {EXTRACT_DIR}/")
        
        # Clean up ZIP file
        os.remove(ZIP_FILE)
        print(f"🗑️  Removed {ZIP_FILE}")
        
        return True
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        return False

def verify_installation():
    """Verify that DiscordChatExporter.Cli.exe exists."""
    exe_path = os.path.join(EXTRACT_DIR, "DiscordChatExporter.Cli.exe")
    
    if os.path.exists(exe_path):
        print(f"\n✅ DiscordChatExporter installed successfully!")
        print(f"Location: {exe_path}")
        return True
    else:
        print(f"\n❌ DiscordChatExporter.Cli.exe not found")
        return False

def main():
    """Main setup function."""
    print("🚀 DiscordChatExporter Setup")
    print("="*60)
    
    # Check if already installed
    if os.path.exists(os.path.join(EXTRACT_DIR, "DiscordChatExporter.Cli.exe")):
        print("✅ DiscordChatExporter is already installed!")
        print(f"Location: {EXTRACT_DIR}/DiscordChatExporter.Cli.exe")
        print("\nTo export your chat, run: export_discord_chat.bat")
        return
    
    # Download
    if not download_chat_exporter():
        return
    
    # Extract
    if not extract_zip():
        return
    
    # Verify
    if verify_installation():
        print("\n" + "="*60)
        print("🎉 Setup Complete!")
        print("="*60)
        print("\nNext step: Export your Discord chat")
        print("  Run: export_discord_chat.bat")
        print("\nOr manually:")
        print(f"  {EXTRACT_DIR}\\DiscordChatExporter.Cli.exe export -t YOUR_TOKEN -c 799704432929406998 -f Json")

if __name__ == "__main__":
    main()
