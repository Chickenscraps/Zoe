"""
Test Layer B Tools
"""
import os
import time
import json
import layer_b_tools
from pathlib import Path

def test_process_tools():
    print("\n--- Testing Process Tools ---")
    
    # 1. Launch Notepad
    print("Launching Notepad...")
    res = layer_b_tools.manage_process("start", "notepad")
    print(res)
    time.sleep(2)
    
    # 2. Check if running
    print("Checking Notepad...")
    res = layer_b_tools.manage_process("check", "notepad")
    print(res)
    
    # 3. Stop Notepad
    print("Stopping Notepad...")
    res = layer_b_tools.manage_process("stop", "notepad")
    print(res)

def test_filesystem_tools():
    print("\n--- Testing Filesystem Tools ---")
    
    # Setup test dir
    test_dir = Path(os.environ["USERPROFILE"]) / "Desktop" / "Clawd_Test_LayerB"
    if test_dir.exists():
        import shutil
        shutil.rmtree(test_dir)
    test_dir.mkdir()
    
    # Create junk files
    (test_dir / "test.txt").write_text("hello")
    (test_dir / "image.png").write_text("fake image")
    (test_dir / "installer.exe").write_text("fake exe")
    
    # 1. Scan
    print("Scanning...")
    stats = layer_b_tools.scan_folder(str(test_dir))
    print(json.dumps(stats, indent=2))
    
    # 2. Propose
    print("Proposing Plan...")
    plan_json = layer_b_tools.propose_organize(str(test_dir))
    print(plan_json)
    
    # 3. Apply
    # We need to extract the JSON only (propose_organize returns text if it finds files, or just plan? 
    # Ah, implementation returns JSON string if matches found, OR text if clean.
    # But wait, my implementation of propose_organize returns the JSON string at the end? 
    # No, it returns `json.dumps(plan)` OR text if empty.
    
    # Review implementation of propose_organize:
    # `return json.dumps(plan, indent=2)` is correct for tool usage? 
    # Actually tool output is usually string. LLM reads it.
    # But `apply_file_ops` expects `plan_json_str`.
    # Let's ensure `propose_organize` returns valid JSON that `apply_file_ops` can read.
    # In my implementation: 
    # `return json.dumps(plan, indent=2)`
    # So yes, it returns a JSON string.
    
    print("Executing Plan...")
    try:
        res = layer_b_tools.apply_file_ops(plan_json)
        print(res)
    except Exception as e:
        print(f"Plan exec failed: {e}")
        
    # Verify results
    if (test_dir / "Documents" / "test.txt").exists():
        print("✅ Text file moved to Documents")
    else:
        print("❌ Text file NOT moved")

    # Cleanup
    # import shutil
    # shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_process_tools()
    test_filesystem_tools()
