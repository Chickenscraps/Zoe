
import os
import sys
import threading
import time
import queue
import wave
import numpy as np
import sounddevice as sd
from pynput import keyboard
from faster_whisper import WhisperModel
import subprocess
try:
    from journal import log_event
except ImportError:
    # Fallback if journal is not available
    print("Warning: 'journal' module not found. Logging will be disabled.", file=sys.stderr)
    def log_event(*args, **kwargs):
        pass # Dummy function to prevent errors

# Configuration
HOTKEY_KEYS = {keyboard.Key.ctrl_l, keyboard.Key.alt_l, keyboard.Key.space}
MODEL_SIZE = "tiny.en" 
SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = "cpu" 
TEMP_WAV = "last_voice_cmd.wav"

print(f"Loading Whisper model ({MODEL_SIZE})...")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type="int8")
print("Model loaded.")

# State
recording = False
audio_queue = queue.Queue()
current_keys = set()

def on_activate():
    global recording
    if not recording:
        print("\n🎤 Recording started... (Hold Ctrl+Alt+Space)")
        recording = True
        log_event("voice.record_start", TEMP_WAV, {"hotkey": "ctrl+alt+space"})

def on_deactivate():
    global recording
    if recording:
        print("🎤 Recording stopped.")
        recording = False
        process_audio_and_transcribe()

def callback(indata, frames, time_info, status):
    if status:
        print(status, file=sys.stderr)
    if recording:
        audio_queue.put(indata.copy())

def record_thread():
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
        while True:
            time.sleep(0.1)

def process_audio_and_transcribe():
    frames = []
    while not audio_queue.empty():
        frames.append(audio_queue.get())
    
    if not frames:
        print("No audio recorded.")
        return

    # Process audio
    audio = np.concatenate(frames, axis=0)
    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)

    # Write real WAV with header
    try:
        with wave.open(TEMP_WAV, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm16.tobytes())
        
        log_event("voice.record_end", TEMP_WAV, {"samples": int(pcm16.shape[0])})
    except Exception as e:
        print(f"Error saving WAV: {e}")
        return

    print("Transcribing...")
    try:
        # Use faster_whisper on the saved file to ensure it's valid
        segments, info = model.transcribe(TEMP_WAV, beam_size=5)
        text = "".join(segment.text for segment in segments).strip()
        
        print(f"User: {text}")
        log_event("voice.transcribe_done", TEMP_WAV, {"text": text})
        
        if text:
            send_to_dispatcher(text)
    except Exception as e:
        print(f"Transcription error: {e}")
        log_event("voice.error", str(e))

def send_to_dispatcher(text):
    print("Sending to Dispatcher...")
    try:
        # Assuming dispatcher.py is in the parent directory as per previous code
        # Wait, the current directory is .agent/skills/clawdbot_persona_extended/
        # dispatcher.py is in C:\Users\josha\OneDrive\Desktop\Clawd\dispatcher.py
        dispatcher_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "dispatcher.py")
        dispatcher_path = os.path.abspath(dispatcher_path)
        
        cmd = ["python", dispatcher_path, text]
        
        env = os.environ.copy()

        result = subprocess.run(cmd, capture_output=True, text=True, env=env, shell=True)
        
        if result.stdout:
            print(f"Agent: {result.stdout.strip()}")
        if result.stderr and result.returncode != 0:
            print(f"Error: {result.stderr}")
            
    except Exception as e:
        print(f"Error sending to dispatcher: {e}")

def on_key_press(key):
    global recording
    # Normalize key for comparison
    if hasattr(key, 'char') and key.char:
        # It's a character key
        pass
    
    current_keys.add(key)
    
    # Check for Ctrl+Alt+Space
    is_ctrl = any(k in current_keys for k in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r])
    is_alt = any(k in current_keys for k in [keyboard.Key.alt_l, keyboard.Key.alt_r])
    is_space = keyboard.Key.space in current_keys
    
    if is_ctrl and is_alt and is_space:
        if not recording:
            on_activate()

def on_key_release(key):
    global recording
    if key in current_keys:
        current_keys.remove(key)
    
    is_ctrl = any(k in current_keys for k in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r])
    is_alt = any(k in current_keys for k in [keyboard.Key.alt_l, keyboard.Key.alt_r])
    is_space = keyboard.Key.space in current_keys
    
    if recording and not (is_ctrl and is_alt and is_space):
        on_deactivate()

if __name__ == "__main__":
    t = threading.Thread(target=record_thread, daemon=True)
    t.start()
    
    print("Voice Agent Ready (WAV Fix Active).")
    print("Hold Ctrl+Alt+Space to speak.")
    
    with keyboard.Listener(on_press=on_key_press, on_release=on_key_release) as listener:
        listener.join()
