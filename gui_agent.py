
import customtkinter as ctk
import subprocess
import threading
import json
import os
from PIL import Image

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ChatMessage(ctk.CTkFrame):
    def __init__(self, master, text, sender="user", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.sender = sender
        
        # Bubble Color
        color = "#2b2b2b" if sender == "agent" else "#1f538d"
        align = "w" if sender == "agent" else "e"
        
        self.bubble = ctk.CTkLabel(
            self, 
            text=text, 
            fg_color=color, 
            corner_radius=15,
            wraplength=350,
            text_color="white",
            padx=10, pady=10
        )
        self.bubble.pack(anchor=align, pady=5, padx=10)

class AgentGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Clawd Desktop Agent")
        self.geometry("400x600")
        self.resizable(False, True)
        
        # --- UI Layout ---
        
        # Header
        self.header = ctk.CTkFrame(self, height=50)
        self.header.pack(fill="x", padx=5, pady=5)
        self.title_label = ctk.CTkLabel(self.header, text="🤖 Clawd Agent", font=("Arial", 16, "bold"))
        self.title_label.pack(pady=10)
        
        # Chat Area (Scrollable)
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Input Area
        self.input_frame = ctk.CTkFrame(self, height=60)
        self.input_frame.pack(fill="x", padx=5, pady=5)
        
        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Type a message...")
        self.entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        self.entry.bind("<Return>", self.send_message)
        
        self.send_btn = ctk.CTkButton(self.input_frame, text="Send", width=60, command=self.send_message)
        self.send_btn.pack(side="right", padx=10, pady=10)
        
        # Initial Message
        self.add_message("Agent", "Hello! I am your desktop assistant. I can control your Calendar, Email, Maps, and more.")

    def add_message(self, sender, text):
        msg = ChatMessage(self.scroll_frame, text, sender=sender.lower())
        msg.pack(fill="x", pady=2)
        self.scroll_frame._parent_canvas.yview_moveto(1.0) # Scroll to bottom

    def send_message(self, event=None):
        text = self.entry.get()
        if not text: return
        
        # 1. Add User Message
        self.add_message("User", text)
        self.entry.delete(0, "end")
        
        # 2. Run Dispatcher in Background
        threading.Thread(target=self.run_agent, args=(text,)).start()

    def run_agent(self, text):
        try:
            # Call dispatcher with --json
            cmd = ["python", "dispatcher.py", text, "--json"]
            env = os.environ.copy()
            env = os.environ.copy()
                
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, shell=True)
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout.strip())
                    response_text = data.get("text", "No response text.")
                    # Handle Media later if type == 'map' etc
                    self.after(0, self.add_message, "Agent", response_text)
                except json.JSONDecodeError:
                    # Fallback to raw text if not JSON
                    self.after(0, self.add_message, "Agent", result.stdout.strip())
            else:
                self.after(0, self.add_message, "Agent", f"Error: {result.stderr}")
                
        except Exception as e:
            self.after(0, self.add_message, "Agent", f"System Error: {e}")

if __name__ == "__main__":
    app = AgentGUI()
    app.mainloop()
