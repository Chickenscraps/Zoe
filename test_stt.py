
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import time

print("Querying devices...")
try:
    print(sd.query_devices())
except Exception as e:
    print(f"Error querying devices: {e}")

print("\nTesting Whisper Load...")
try:
    model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    print("Whisper loaded.")
except Exception as e:
    print(f"Error loading Whisper: {e}")
    exit(1)

print("\nRecording 3 seconds of audio...")
fs = 16000
duration = 3  # seconds
try:
    myrecording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()  # Wait until recording is finished
    print("Recording finished.")
    
    # Transcribe
    print("Transcribing...")
    segments, info = model.transcribe(myrecording.flatten().astype(np.float32), beam_size=5)
    for segment in segments:
        print("[Text]: %s" % segment.text)

except Exception as e:
    print(f"Recording/Transcription failed: {e}")
