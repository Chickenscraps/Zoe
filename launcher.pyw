"""
Edge Factory Command Center - Desktop Launcher
Double-click to launch. Manages all services from one window.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from pathlib import Path

# ── Resolve project root ──────────────────────────────────────
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

# ── Safety phrase for live trading ────────────────────────────
CONFIRM_PHRASE = "I UNDERSTAND THIS IS REAL MONEY"

# ── Service Definitions ───────────────────────────────────────

SERVICES = {
    "edge_factory": {
        "label": "Edge Factory",
        "cmd": [sys.executable, "-m", "services.edge_factory"],
        "cwd": str(ROOT),
        "env_extra": {"EDGE_FACTORY_MODE": "paper"},
        "color": "#22c55e",  # green
    },
    "discord_bot": {
        "label": "Discord Bot (Clawdbot)",
        "cmd": [sys.executable, "clawdbot.py"],
        "cwd": str(ROOT),
        "env_extra": {},
        "color": "#6366f1",  # indigo
    },
    "dashboard": {
        "label": "Dashboard (Zoe Terminal)",
        "cmd": ["npm.cmd", "run", "dev"],
        "cwd": str(ROOT / "zoe-terminal"),
        "env_extra": {},
        "color": "#f59e0b",  # amber
        "url": "http://localhost:5180",
        "shell": True,
    },
    "host_bridge": {
        "label": "Host Bridge API",
        "cmd": [sys.executable, "host_bridge.py"],
        "cwd": str(ROOT),
        "env_extra": {},
        "color": "#8b5cf6",  # violet
    },
    "api_server": {
        "label": "API Server (Port 8000)",
        "cmd": [sys.executable, "AGENT PERSONA SKILL/server.py"],
        "cwd": str(ROOT),
        "env_extra": {},
        "color": "#ec4899",  # pink
    },
    "investing_sync": {
        "label": "Investing Account Sync",
        "cmd": [sys.executable, "services/investing_sync.py"],
        "cwd": str(ROOT),
        "env_extra": {},
        "color": "#0ea5e9",  # light blue
    },
}


class ServiceManager:
    """Manages a subprocess for a single service."""

    def __init__(self, name: str, cfg: dict, log_callback):
        self.name = name
        self.cfg = cfg
        self.log = log_callback
        self.process: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_flag = False

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self):
        if self.running:
            self.log(self.name, "[WARN] Already running\n")
            return

        env = os.environ.copy()
        env.update(self.cfg.get("env_extra", {}))
        # Force UTF-8 for subprocess output
        env["PYTHONIOENCODING"] = "utf-8"

        self._stop_flag = False
        try:
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            use_shell = self.cfg.get("shell", False)
            self.process = subprocess.Popen(
                self.cfg["cmd"],
                cwd=self.cfg["cwd"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creation_flags,
                shell=use_shell,
            )
            self.log(self.name, f"[START] PID {self.process.pid}\n")
            self._reader_thread = threading.Thread(
                target=self._read_output, daemon=True
            )
            self._reader_thread.start()
        except Exception as e:
            self.log(self.name, f"[ERR] Failed to start: {e}\n")

    def stop(self):
        if not self.running:
            return
        self._stop_flag = True
        self.log(self.name, "[STOP] Shutting down...\n")
        
        try:
            pid = self.process.pid
            if sys.platform == "win32":
                # Force kill the entire process tree
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            else:
                self.process.terminate()
                
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
                
        self.log(self.name, "[STOP] Stopped\n")
        self.process = None

    def _read_output(self):
        try:
            for line in self.process.stdout:
                if self._stop_flag:
                    break
                self.log(self.name, line)
        except Exception:
            pass
        if self.process and self.process.poll() is not None and not self._stop_flag:
            code = self.process.returncode
            self.log(self.name, f"[EXIT] Process exited with code {code}\n")
            self.process = None


class LauncherApp:
    """Main GUI application."""

    WINDOW_TITLE = "Edge Factory Command Center"
    WINDOW_SIZE = "900x700"
    BG = "#0f0f0f"
    FG = "#e4e4e7"
    ACCENT = "#22c55e"
    PANEL_BG = "#1a1a1a"
    BTN_BG = "#27272a"
    BTN_HOVER = "#3f3f46"
    FONT = ("Consolas", 10)
    FONT_BOLD = ("Consolas", 10, "bold")
    FONT_HEADER = ("Consolas", 14, "bold")
    FONT_SMALL = ("Consolas", 9)

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(self.WINDOW_TITLE)
        self.root.geometry(self.WINDOW_SIZE)
        self.root.configure(bg=self.BG)
        self.root.minsize(700, 500)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self.managers: dict[str, ServiceManager] = {}
        self.buttons: dict[str, dict] = {}
        self._trading_mode = "paper"  # "paper" or "live"

        self._build_ui()

        for name, cfg in SERVICES.items():
            self.managers[name] = ServiceManager(name, cfg, self._log)

        self._update_status_loop()

    def _build_ui(self):
        # ── Header ─────────────────────────────────────────
        header = tk.Frame(self.root, bg=self.BG)
        header.pack(fill=tk.X, padx=16, pady=(16, 8))

        tk.Label(
            header,
            text="EDGE FACTORY",
            font=self.FONT_HEADER,
            fg=self.ACCENT,
            bg=self.BG,
        ).pack(side=tk.LEFT)

        tk.Label(
            header,
            text="  Command Center",
            font=("Consolas", 14),
            fg="#71717a",
            bg=self.BG,
        ).pack(side=tk.LEFT)

        stop_all_btn = tk.Button(
            header,
            text="STOP ALL",
            font=self.FONT_BOLD,
            fg="#ef4444",
            bg="#2a1a1a",
            activeforeground="#ef4444",
            activebackground="#3a2020",
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._stop_all,
        )
        stop_all_btn.pack(side=tk.RIGHT)

        start_all_btn = tk.Button(
            header,
            text="START ALL",
            font=self.FONT_BOLD,
            fg=self.ACCENT,
            bg="#1a2a1a",
            activeforeground=self.ACCENT,
            activebackground="#203020",
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._start_all,
        )
        start_all_btn.pack(side=tk.RIGHT, padx=(0, 8))

        # ── Service Cards ──────────────────────────────────
        cards_frame = tk.Frame(self.root, bg=self.BG)
        cards_frame.pack(fill=tk.X, padx=16, pady=(8, 4))

        for name, cfg in SERVICES.items():
            card = tk.Frame(cards_frame, bg=self.PANEL_BG, highlightthickness=1, highlightbackground="#27272a")
            card.pack(fill=tk.X, pady=3)

            # Status dot
            dot = tk.Label(
                card,
                text=" -- ",
                font=self.FONT_SMALL,
                fg="#71717a",
                bg=self.PANEL_BG,
                width=6,
            )
            dot.pack(side=tk.LEFT, padx=(8, 4), pady=6)

            # Service name
            label_widget = tk.Label(
                card,
                text=cfg["label"],
                font=self.FONT_BOLD,
                fg=cfg["color"],
                bg=self.PANEL_BG,
                anchor="w",
            )
            label_widget.pack(side=tk.LEFT, padx=4, pady=6)

            # Stop button
            stop_btn = tk.Button(
                card,
                text="Stop",
                font=self.FONT_SMALL,
                fg="#ef4444",
                bg=self.BTN_BG,
                activeforeground="#ef4444",
                activebackground=self.BTN_HOVER,
                relief=tk.FLAT,
                bd=0,
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda n=name: self._stop_service(n),
            )
            stop_btn.pack(side=tk.RIGHT, padx=(2, 8), pady=6)

            # Start button
            start_btn = tk.Button(
                card,
                text="Start",
                font=self.FONT_SMALL,
                fg=self.ACCENT,
                bg=self.BTN_BG,
                activeforeground=self.ACCENT,
                activebackground=self.BTN_HOVER,
                relief=tk.FLAT,
                bd=0,
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda n=name: self._start_service(n),
            )
            start_btn.pack(side=tk.RIGHT, padx=2, pady=6)

            # Open URL button (for dashboard)
            if "url" in cfg:
                url_btn = tk.Button(
                    card,
                    text="Open",
                    font=self.FONT_SMALL,
                    fg="#60a5fa",
                    bg=self.BTN_BG,
                    activeforeground="#60a5fa",
                    activebackground=self.BTN_HOVER,
                    relief=tk.FLAT,
                    bd=0,
                    padx=8,
                    pady=2,
                    cursor="hand2",
                    command=lambda u=cfg["url"]: self._open_url(u),
                )
                url_btn.pack(side=tk.RIGHT, padx=2, pady=6)

            # Paper/Live toggle for Edge Factory
            if name == "edge_factory":
                self._mode_label = tk.Label(
                    card,
                    text="PAPER",
                    font=self.FONT_BOLD,
                    fg="#fbbf24",
                    bg="#2a2a1a",
                    padx=6,
                    pady=1,
                )
                self._mode_label.pack(side=tk.RIGHT, padx=4, pady=6)

                toggle_btn = tk.Button(
                    card,
                    text="Toggle Live",
                    font=self.FONT_SMALL,
                    fg="#f59e0b",
                    bg=self.BTN_BG,
                    activeforeground="#f59e0b",
                    activebackground=self.BTN_HOVER,
                    relief=tk.FLAT,
                    bd=0,
                    padx=8,
                    pady=2,
                    cursor="hand2",
                    command=self._toggle_trading_mode,
                )
                toggle_btn.pack(side=tk.RIGHT, padx=2, pady=6)

            self.buttons[name] = {
                "dot": dot,
                "start": start_btn,
                "stop": stop_btn,
                "label": label_widget,
            }

        # ── Log Tabs ───────────────────────────────────────
        log_frame = tk.Frame(self.root, bg=self.BG)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(8, 16))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background=self.BG, borderwidth=0)
        style.configure(
            "Dark.TNotebook.Tab",
            background=self.BTN_BG,
            foreground=self.FG,
            padding=[10, 4],
            font=self.FONT_SMALL,
        )
        style.map(
            "Dark.TNotebook.Tab",
            background=[("selected", self.PANEL_BG)],
            foreground=[("selected", self.ACCENT)],
        )

        self.notebook = ttk.Notebook(log_frame, style="Dark.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.logs: dict[str, scrolledtext.ScrolledText] = {}
        for name, cfg in SERVICES.items():
            tab = tk.Frame(self.notebook, bg=self.PANEL_BG)
            self.notebook.add(tab, text=f" {cfg['label'].split('(')[0].strip()} ")

            log_widget = scrolledtext.ScrolledText(
                tab,
                bg="#0a0a0a",
                fg="#a1a1aa",
                font=self.FONT_SMALL,
                insertbackground=self.FG,
                selectbackground="#27272a",
                relief=tk.FLAT,
                bd=8,
                wrap=tk.WORD,
                state=tk.DISABLED,
            )
            log_widget.pack(fill=tk.BOTH, expand=True)
            self.logs[name] = log_widget

    def _toggle_trading_mode(self):
        """Toggle between paper and live trading."""
        ef_mgr = self.managers["edge_factory"]

        if self._trading_mode == "paper":
            # Switching to LIVE — require confirmation
            answer = simpledialog.askstring(
                "LIVE TRADING CONFIRMATION",
                "You are about to enable LIVE trading with REAL MONEY.\n\n"
                "This will place real orders on your Robinhood account.\n\n"
                f'Type exactly: {CONFIRM_PHRASE}\n',
                parent=self.root,
            )

            if answer != CONFIRM_PHRASE:
                messagebox.showwarning(
                    "Cancelled",
                    "Live trading NOT enabled. Phrase did not match.",
                    parent=self.root,
                )
                return

            # Check for RH credentials
            rh_key = os.environ.get("RH_CRYPTO_API_KEY", "")
            rh_seed = os.environ.get("RH_CRYPTO_PRIVATE_KEY_SEED", "")
            if not rh_key or not rh_seed:
                messagebox.showerror(
                    "Missing Credentials",
                    "Live trading requires RH_CRYPTO_API_KEY and "
                    "RH_CRYPTO_PRIVATE_KEY_SEED in your .env file.",
                    parent=self.root,
                )
                return

            self._trading_mode = "live"
            SERVICES["edge_factory"]["env_extra"] = {
                "EDGE_FACTORY_MODE": "live",
                "RH_LIVE_CONFIRM": CONFIRM_PHRASE,
            }
            self._mode_label.config(text="LIVE", fg="#ef4444", bg="#2a1a1a")
            self._log("edge_factory", "[MODE] Switched to LIVE trading\n")

            # Restart if running
            if ef_mgr.running:
                self._log("edge_factory", "[MODE] Restarting with live mode...\n")
                threading.Thread(target=self._restart_edge_factory, daemon=True).start()

        else:
            # Switching back to PAPER — no confirmation needed
            self._trading_mode = "paper"
            SERVICES["edge_factory"]["env_extra"] = {"EDGE_FACTORY_MODE": "paper"}
            self._mode_label.config(text="PAPER", fg="#fbbf24", bg="#2a2a1a")
            self._log("edge_factory", "[MODE] Switched to PAPER trading\n")

            if ef_mgr.running:
                self._log("edge_factory", "[MODE] Restarting with paper mode...\n")
                threading.Thread(target=self._restart_edge_factory, daemon=True).start()

    def _restart_edge_factory(self):
        """Stop then start Edge Factory (runs in thread)."""
        self.managers["edge_factory"].stop()
        time.sleep(1)
        self.managers["edge_factory"].start()

    def _log(self, service_name: str, text: str):
        """Thread-safe log append."""
        def _append():
            widget = self.logs.get(service_name)
            if widget is None:
                return
            widget.config(state=tk.NORMAL)
            widget.insert(tk.END, text)
            widget.see(tk.END)
            line_count = int(widget.index("end-1c").split(".")[0])
            if line_count > 5000:
                widget.delete("1.0", "2000.0")
            widget.config(state=tk.DISABLED)

        self.root.after(0, _append)

    def _start_service(self, name: str):
        threading.Thread(target=self.managers[name].start, daemon=True).start()

    def _stop_service(self, name: str):
        threading.Thread(target=self.managers[name].stop, daemon=True).start()

    def _start_all(self):
        for name in SERVICES:
            if not self.managers[name].running:
                self._start_service(name)
                time.sleep(0.3)

    def _stop_all(self):
        for name in SERVICES:
            self._stop_service(name)

    def _open_url(self, url: str):
        import webbrowser
        webbrowser.open(url)

    def _update_status_loop(self):
        """Update status dots every 500ms."""
        for name, mgr in self.managers.items():
            dot = self.buttons[name]["dot"]
            if mgr.running:
                dot.config(text="LIVE", fg="#22c55e")
            else:
                dot.config(text="OFF", fg="#71717a")
        self.root.after(500, self._update_status_loop)

    def _on_close(self):
        """Cleanup all services on window close."""
        for mgr in self.managers.values():
            if mgr.running:
                try:
                    mgr.stop()
                except Exception:
                    pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def enforce_single_instance():
    """Ensure only one instance of the launcher is running."""
    import socket
    
    # Arbitrary high port for the lock
    LOCK_PORT = 64999
    
    global _SINGLE_INSTANCE_SOCKET
    _SINGLE_INSTANCE_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        # Try to bind to localhost on the lock port
        _SINGLE_INSTANCE_SOCKET.bind(('127.0.0.1', LOCK_PORT))
    except OSError:
        # Binding failed, meaning port is in use -> another instance is running
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("Already Running", "Edge Factory Command Center is already open.")
        root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    enforce_single_instance()
    app = LauncherApp()
    app.run()
