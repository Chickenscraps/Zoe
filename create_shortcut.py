"""Creates a desktop shortcut for Edge Factory Command Center."""
import os
import sys
from pathlib import Path

try:
    import winshell
    from win32com.client import Dispatch
except ImportError:
    print("[INFO] Installing pywin32 + winshell for shortcut creation...")
    os.system(f"{sys.executable} -m pip install pywin32 winshell -q")
    import winshell
    from win32com.client import Dispatch

ROOT = Path(__file__).resolve().parent
desktop = winshell.desktop()
shortcut_path = os.path.join(desktop, "Edge Factory.lnk")

shell = Dispatch("WScript.Shell")
shortcut = shell.CreateShortCut(shortcut_path)
shortcut.Targetpath = sys.executable.replace("python.exe", "pythonw.exe")
shortcut.Arguments = f'"{ROOT / "launcher.pyw"}"'
shortcut.WorkingDirectory = str(ROOT)
shortcut.Description = "Edge Factory Command Center"
shortcut.save()

print(f"[OK] Desktop shortcut created: {shortcut_path}")
