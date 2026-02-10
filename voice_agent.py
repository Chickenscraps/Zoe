
import os
import sys
import threading
import time
import queue
import numpy as np
import sounddevice as sd
from pynput import keyboard
from faster_whisper import WhisperModel
import subprocess

# Configuration
HOTKEY = '<ctrl>+<alt>+<space>'
MODEL_SIZE = "tiny.en" 
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = "cpu" # or "cuda" if nvidia available

print(f"Loading Whisper model ({MODEL_SIZE})...")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type="int8")
print("Model loaded.")

# State
recording = False
audio_queue = queue.Queue()
audio_buffer = []

def on_activate():
    global recording, audio_buffer
    if not recording:
        print("\n[Recording started] (Hold Ctrl+Alt+Space)")
        recording = True
        audio_buffer = []
        # Start recording stream setup is implicitly handled by the callback or loop
    else:
        # Already recording, do nothing (wait for release)
        pass

def on_deactivate():
    global recording
    if recording:
        print("[Recording stopped]")
        recording = False
        process_audio()

def on_press(key):
    pass # Managed by GlobalHotKeys

def on_release(key):
    pass # Managed by GlobalHotKeys

# Audio Callback
def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    if recording:
        audio_queue.put(indata.copy())

def record_thread():
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
        while True:
            # Keep stream alive
            time.sleep(0.1)

def process_audio():
    global audio_buffer
    
    # Collect all data from queue
    while not audio_queue.empty():
        audio_buffer.append(audio_queue.get())
    
    if not audio_buffer:
        print("No audio recorded.")
        return

    # Concatenate
    data = np.concatenate(audio_buffer, axis=0).flatten().astype(np.float32)
    audio_buffer = [] # Clear buffer
    
    if len(data) < SAMPLE_RATE * 0.5: # Ignore < 0.5s
        print("Audio too short.")
        return

    print("Transcribing...")
    segments, info = model.transcribe(data, beam_size=5)
    
    text = ""
    for segment in segments:
        text += segment.text
    
    text = text.strip()
    print(f"User: {text}")
    
    if text:
        send_to_openclaw(text)

def send_to_openclaw(text):
    print("Sending to Dispatcher...")
    try:
        # Construct command
        # Call dispatcher.py which handles routing
        cmd = ["python", "dispatcher.py", text]
        
        env = os.environ.copy()

        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, shell=True)
        
        if result.stdout:
            print(f"Agent: {result.stdout.strip()}")
        if result.stderr and result.returncode != 0:
            print(f"Error: {result.stderr}")
            
    except Exception as e:
        print(f"Error sending to agent: {e}")

# Hotkey Listener
# Note: pynput GlobalHotKeys doesn't perfectly support "press and hold" logical mapping directly in a simple way 
# without handling press/release events manually for the specific combo. 
# GlobalHotKeys triggers on_activate when ALL keys are pressed.
# We need to detect RELEASE of the combo to stop recording.
# So we'll use a slightly lower level listener for robustness or explicit key checking.

# Improved Logic:
# Use Listener to track state of Ctrl, Alt, Space.

current_keys = set()
COMBINATION = {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.Key.space}
# Also accept right side keys
COMBINATION_ALT = {keyboard.Key.ctrl_r, keyboard.Key.alt_r, keyboard.Key.space}

def on_key_press(key):
    global recording
    if key in COMBINATION or key in COMBINATION_ALT or key == keyboard.Key.space: # Space is shared
        current_keys.add(key)
        
        # Check if any valid combo is active
        # Attempt to match sets. Note that 'Key.ctrl_l' and 'Key.ctrl' might differ based on OS.
        # Simplified: Check if we have Ctrl+Alt+Space
        
        # Normalize keys if needed or just check presence
        # Simplification: just check if 3 keys including space and some ctrl/alt are held.
        
        is_ctrl = (keyboard.Key.ctrl_l in current_keys) or (keyboard.Key.ctrl_r in current_keys)
        is_alt = (keyboard.Key.alt_l in current_keys) or (keyboard.Key.alt_r in current_keys)
        is_space = (keyboard.Key.space in current_keys)
        
        if is_ctrl and is_alt and is_space:
            if not recording:
                on_activate()

def on_key_release(key):
    global recording
    try:
        current_keys.remove(key)
    except KeyError:
        pass
    
    # If any key of the combo is released, stop recording
    # (Strictly speaking, if you release space, you stop talking)
    
    is_ctrl = (keyboard.Key.ctrl_l in current_keys) or (keyboard.Key.ctrl_r in current_keys)
    is_alt = (keyboard.Key.alt_l in current_keys) or (keyboard.Key.alt_r in current_keys)
    is_space = (keyboard.Key.space in current_keys)
    
    if recording and not (is_ctrl and is_alt and is_space):
        on_deactivate()

# Main
if __name__ == "__main__":
    # Start audio thread
    t = threading.Thread(target=record_thread, daemon=True)
    t.start()
    
    print("Voice Agent Ready.")
    print("Hold Ctrl+Alt+Space to speak.")
    
    with keyboard.Listener(on_press=on_key_press, on_release=on_key_release) as listener:
        listener.join()
