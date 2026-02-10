"""
Text-to-Speech Service for Clawdbot
Uses edge-tts for high-quality voice synthesis
"""
import os
import io
import asyncio
import tempfile
from typing import Optional
from pathlib import Path
from datetime import datetime

import discord

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("⚠️ edge-tts not available")

# ============================================================================
# Configuration
# ============================================================================

# Voice options - pick one that sounds natural
VOICE_OPTIONS = {
    "male_us": "en-US-GuyNeural",
    "female_us": "en-US-JennyNeural",
    "male_uk": "en-GB-RyanNeural",
    "female_uk": "en-GB-SoniaNeural",
    "male_au": "en-AU-WilliamNeural",
}

DEFAULT_VOICE = "en-US-JennyNeural"  # Natural female voice for Zoe
RATE = "+5%"  # Slightly faster for natural feel
PITCH = "+0Hz"

TEMP_AUDIO_DIR = Path(tempfile.gettempdir()) / "clawdbot_tts"
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# TTS Service
# ============================================================================

class TTSService:
    """Text-to-speech using edge-tts."""
    
    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice
        self.rate = RATE
        self.pitch = PITCH
        self._queue: asyncio.Queue = asyncio.Queue()
        self._current_audio: Optional[discord.FFmpegPCMAudio] = None
        self._is_speaking: bool = False
    
    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
    
    async def synthesize(self, text: str) -> Optional[Path]:
        """Convert text to audio file."""
        if not EDGE_TTS_AVAILABLE:
            print(f"⚠️ TTS unavailable, would say: {text}")
            return None
        
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            audio_path = TEMP_AUDIO_DIR / f"tts_{timestamp}.mp3"
            
            # Generate speech
            communicate = edge_tts.Communicate(
                text,
                self.voice,
                rate=self.rate,
                pitch=self.pitch
            )
            
            await communicate.save(str(audio_path))
            
            return audio_path
        except Exception as e:
            print(f"❌ TTS synthesis failed: {e}")
            return None
    
    async def speak_in_channel(
        self,
        voice_client: discord.VoiceClient,
        text: str,
        wait: bool = True
    ) -> bool:
        """Speak text in the voice channel."""
        if not voice_client or not voice_client.is_connected():
            return False
        
        # Skip if already speaking
        if voice_client.is_playing():
            # Queue for later
            await self._queue.put(text)
            return True
        
        # Synthesize audio
        audio_path = await self.synthesize(text)
        if not audio_path:
            return False
        
        try:
            self._is_speaking = True
            
            # Play audio
            audio_source = discord.FFmpegPCMAudio(str(audio_path))
            
            # Callback to cleanup
            def after_play(error):
                self._is_speaking = False
                # Clean up temp file
                try:
                    audio_path.unlink()
                except:
                    pass
                
                if error:
                    print(f"❌ Playback error in after_play: {error}")
                else:
                    print("✅ Playback finished successfully (according to discord.py)")
            
            print(f"▶️ Playing audio source: {audio_path}")
            # Explicit FFmpeg path to avoid resolution issues
            FFMPEG_PATH = r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"
            
            voice_client.play(
                discord.FFmpegPCMAudio(str(audio_path), executable=FFMPEG_PATH), 
                after=after_play
            )
            
            if wait:
                # Wait for playback to complete
                start_time = datetime.now()
                while voice_client.is_playing():
                    await asyncio.sleep(0.1)
                    if (datetime.now() - start_time).total_seconds() > 30:
                        print("⚠️ Playback timed out (stuck?)")
                        break
                print("⏹️ Playback loop ended")
            
            return True
            return True
        except Exception as e:
            print(f"❌ Playback failed: {e}")
            self._is_speaking = False
            return False

    def stop_speaking(self, voice_client: discord.VoiceClient):
        """Stop current playback strictly."""
        if voice_client and voice_client.is_playing():
            voice_client.stop()
        self.clear_queue()
        self._is_speaking = False
        print("🛑 Stopped speaking (Interrupted)")
    
    async def process_queue(self, voice_client: discord.VoiceClient):
        """Process queued TTS messages."""
        while True:
            try:
                text = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self.speak_in_channel(voice_client, text, wait=True)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"⚠️ Queue processing error: {e}")
    
    def clear_queue(self):
        """Clear pending TTS messages."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
    
    @staticmethod
    async def list_voices() -> list:
        """List available voices."""
        if not EDGE_TTS_AVAILABLE:
            return []
        
        voices = await edge_tts.list_voices()
        return [
            {
                "name": v["ShortName"],
                "gender": v["Gender"],
                "locale": v["Locale"]
            }
            for v in voices
            if v["Locale"].startswith("en-")
        ]
    
    def cleanup(self):
        """Clean up temp audio files."""
        for f in TEMP_AUDIO_DIR.glob("tts_*.mp3"):
            try:
                f.unlink()
            except:
                pass


# ============================================================================
# Voice Activity Detection Helper
# ============================================================================

class VADHelper:
    """Simple VAD helper for interruption prevention."""
    
    def __init__(self):
        self._user_speaking = False
        self._last_speech_time = None
        self._silence_threshold_ms = 500  # 500ms of silence = not speaking
    
    def on_user_speaking(self, user_id: str, speaking: bool):
        """Track when users are speaking."""
        if speaking:
            self._user_speaking = True
            self._last_speech_time = datetime.now()
        else:
            self._last_speech_time = datetime.now()
    
    def is_anyone_speaking(self) -> bool:
        """Check if anyone is currently speaking."""
        if not self._user_speaking:
            return False
        
        if self._last_speech_time:
            elapsed_ms = (datetime.now() - self._last_speech_time).total_seconds() * 1000
            if elapsed_ms > self._silence_threshold_ms:
                self._user_speaking = False
                return False
        
        return True
    
    def should_bot_speak(self) -> bool:
        """Determine if bot should speak now (no interruption)."""
        return not self.is_anyone_speaking()


# ============================================================================
# Test
# ============================================================================

async def test_tts():
    """Test TTS synthesis."""
    print("Testing TTS...")
    
    service = TTSService()
    
    # List available voices
    voices = await service.list_voices()
    print(f"Available English voices: {len(voices)}")
    for v in voices[:5]:
        print(f"  - {v['name']} ({v['gender']}, {v['locale']})")
    
    # Test synthesis
    audio_path = await service.synthesize("Hello! This is Clawdbot testing the TTS system.")
    if audio_path:
        print(f"✅ Audio generated: {audio_path}")
        print(f"   Size: {audio_path.stat().st_size} bytes")
    else:
        print("❌ Synthesis failed")
    
    service.cleanup()


if __name__ == "__main__":
    asyncio.run(test_tts())
