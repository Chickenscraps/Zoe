"""
Voice Worker Module for Clawdbot
Handles voice channel presence, transcription, and TTS

Target Channel: 1174052382057963623
"""
import os
import asyncio
import logging
import uuid
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import json
from thought_logger import thought_logger

import discord
from discord.ext import commands

try:
    from discord.ext import voice_recv
    VOICE_RECV_AVAILABLE = True
except ImportError:
    VOICE_RECV_AVAILABLE = False
    print("⚠️ discord-ext-voice-recv not available")

try:
    from transcription_service import transcription_service
    TRANSCRIPTION_AVAILABLE = True
except ImportError:
    TRANSCRIPTION_AVAILABLE = False
    print("⚠️ Transcription service not available")

import wave
import audioop
import time

# ============================================================================
# Configuration
# ============================================================================

TARGET_VOICE_CHANNEL = 1174052382057963623
EMPTY_CHANNEL_COOLDOWN_S = 60
MANUAL_LEAVE_POLICY = "rejoin_after_empty"  # or "disabled_until_explicit"

# ============================================================================
# State Management
# ============================================================================

class VoicePresenceState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    LEAVING_COOLDOWN = "leaving_cooldown"
    MANUAL_LEFT = "manual_left"

@dataclass
class VoiceSessionState:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: int = TARGET_VOICE_CHANNEL
    state: VoicePresenceState = VoicePresenceState.DISCONNECTED
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    participants: List[str] = field(default_factory=list)
    listening_enabled: bool = False
    speaking_enabled: bool = False
    speaking_mode: str = "push_to_talk"  # or "auto"
    logging_enabled: bool = False
    last_activity: Optional[datetime] = None
    manual_leave_flag: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "state": self.state.value,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "disconnected_at": self.disconnected_at.isoformat() if self.disconnected_at else None,
            "participants": self.participants,
            "listening_enabled": self.listening_enabled,
            "speaking_enabled": self.speaking_enabled,
            "speaking_mode": self.speaking_mode,
            "logging_enabled": self.logging_enabled,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "manual_leave_flag": self.manual_leave_flag
        }

@dataclass
class TranscriptEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    speaker_id: str = ""
    profile_id: str = ""
    text: str = ""
    confidence: float = 0.0
    duration_ms: int = 0
    source_tag: str = "discord_voice"
    mood_signals: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "speaker_id": self.speaker_id,
            "profile_id": self.profile_id,
            "text": self.text,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "source_tag": self.source_tag,
            "mood_signals": self.mood_signals
        }

# ============================================================================
# Voice Worker
# ============================================================================

# Import TTS service
try:
    from tts_service import TTSService, VADHelper
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    print("⚠️ TTS service not available")

# ============================================================================
# Audio Sink (Whisper)
# ============================================================================

class AudioBuffer:
    """Buffer for collecting audio data per user."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.buffer = bytearray()
        self.last_packet_time = time.time()
        self.start_time = time.time()
    
    def add_data(self, data: bytes):
        self.buffer.extend(data)
        self.last_packet_time = time.time()
    
    def is_silence_timeout(self, threshold: float = 0.5) -> bool:
        """Check if user has been silent for threshold seconds."""
        return (time.time() - self.last_packet_time) > threshold
    
    def duration(self) -> float:
        """Duration in seconds (assuming 48kHz stereo 16-bit)."""
        # 48000 Hz * 2 channels * 2 bytes = 192000 bytes/sec
        return len(self.buffer) / 192000

class WhisperSink(voice_recv.AudioSink):
    """Sink that buffers audio and sends to Whisper. Also handles VAD."""
    def __init__(self, callback, voice_worker):
        super().__init__()
        self.callback = callback
        self.voice_worker = voice_worker
        self.user_buffers = {}
        self.last_speech_time = {}
        # VAD settings
        self.rms_threshold = 200
        
        self.buffers: Dict[int, AudioBuffer] = {}
        self.processing_task = asyncio.create_task(self._process_buffers())
        
    def wants_opus(self) -> bool:
        return False  # We want PCM
    
    def write(self, user, data):
        """Handle incoming audio packet (voice_recv.AudioSink signature)."""
        if user is None:
            return
            
        # AudioData from voice_recv has .pcm attribute (bytes)
        pcm_data = data.pcm 
        
        # Simple RMS calculation for VAD
        rms = audioop.rms(pcm_data, 2)
        
        if rms > self.rms_threshold:
            # Detect speech -> Interrupt Bot!
            if self.voice_worker and self.voice_worker.is_speaking:
                print(f"🎤 Interruption detected from {user.name} (RMS: {rms})")
                self.voice_worker.interrupt()
        
        user_id = user.id
        if user_id not in self.buffers:
            self.buffers[user_id] = AudioBuffer(user_id)
            
        self.buffers[user_id].add_data(pcm_data)
    
    async def _process_buffers(self):
        """Periodically check buffers for silence/completion."""
        try:
            while True:
                await asyncio.sleep(0.1)
                
                # Check all buffers
                current_time = time.time()
                to_process = []
                
                for user_id, buffer in list(self.buffers.items()):
                    # If silent for >1s or too long (>15s), process it
                    is_silence = buffer.is_silence_timeout(1.0)
                    is_too_long = buffer.duration() > 15.0
                    
                    if (is_silence and buffer.duration() > 0.5) or is_too_long:
                        to_process.append(user_id)
                
                for user_id in to_process:
                    buffer = self.buffers.pop(user_id)
                    asyncio.create_task(self._transcribe_buffer(buffer))
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ Sink processing error: {e}")

    async def _transcribe_buffer(self, buffer: AudioBuffer):
        """Save buffer to file and transcribe."""
        if not TRANSCRIPTION_AVAILABLE:
            return

        try:
            # Save to temporary WAV
            filename = f"voice_{buffer.user_id}_{int(time.time())}.wav"
            filepath = os.path.join(tempfile.gettempdir(), filename)
            
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(2)  # Stereo
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(48000)
                wf.writeframes(buffer.buffer)
            
            # Transcribe
            # We assume transcription_service can handle this file
            result = await transcription_service.transcribe_file(filepath)
            
            # Clean up
            try:
                os.remove(filepath)
            except:
                pass
            
            if result.get("text"):
                text = result["text"].strip()
                if len(text) > 0:
                    conf = result.get("confidence", 0.0)
                    await self.callback(str(buffer.user_id), text, conf)
                    
        except Exception as e:
            print(f"❌ Transcription task failed: {e}")

    def cleanup(self):
        if self.processing_task:
            self.processing_task.cancel()

class VoiceWorker:
    """Manages voice channel presence, transcription, and TTS."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = VoiceSessionState()
        self.voice_client: Optional[discord.VoiceClient] = None
        self.leave_task: Optional[asyncio.Task] = None
        self.transcripts: List[TranscriptEvent] = []
        self._tts_queue: asyncio.Queue = asyncio.Queue()
        self._someone_speaking: bool = False
        self.sink: Optional[WhisperSink] = None # Added for explicit sink management
        
        # TTS integration
        self.tts: Optional[TTSService] = TTSService() if TTS_AVAILABLE else None
        self.vad: VADHelper = VADHelper() if TTS_AVAILABLE else None
        
        # Start loneliness check
        self.loneliness_task = self.bot.loop.create_task(self._check_loneliness())

    async def _check_loneliness(self):
        """Periodically check if bot is alone and should leave."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await asyncio.sleep(30)  # Check every 30s
                
                if self.is_connected and self.voice_client and self.voice_client.channel:
                    members = self.voice_client.channel.members
                    non_bots = [m for m in members if not m.bot]
                    
                    if len(non_bots) == 0:
                        print("Runaway bot detected in empty channel. Leaving...")
                        await self.leave(reason="loneliness_check")
            except Exception as e:
                print(f"⚠️ Loneliness check error: {e}")
                await asyncio.sleep(30)
    
    @property
    def is_speaking(self) -> bool:
        return self.tts.is_speaking if self.tts else False

    def interrupt(self):
        """Interrupt the bot (stop speaking)."""
        if self.voice_client and self.is_speaking:
            self.tts.stop_speaking(self.voice_client)
            print("🛑 Bot speaking interrupted.")
    
    @property
    def is_connected(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_connected()
        
    async def check_existing_sessions(self):
        """Check if users are already in the channel on startup."""
        channel = self.bot.get_channel(TARGET_VOICE_CHANNEL)
        if not channel:
            return
            
        non_bot_members = [m for m in channel.members if not m.bot]
        
        if len(non_bot_members) > 0:
            print(f"👀 Found {len(non_bot_members)} users in voice. Auto-joining.")
            for member in non_bot_members:
                await self._on_user_joined(member, channel)
    
    async def handle_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """Handle voice state changes for auto-join/leave."""
        # Ignore bot's own events
        if member.bot:
            return
        
        target_channel = self.bot.get_channel(TARGET_VOICE_CHANNEL)
        if not target_channel:
            return
        
        # User joined target channel
        if after.channel and after.channel.id == TARGET_VOICE_CHANNEL:
            await self._on_user_joined(member, target_channel)
        
        # User left target channel
        if before.channel and before.channel.id == TARGET_VOICE_CHANNEL:
            await self._on_user_left(member, target_channel)
    
    async def _on_user_joined(self, member: discord.Member, channel: discord.VoiceChannel):
        """Handle user joining the target channel."""
        # Add to participants
        if str(member.id) not in self.session.participants:
            self.session.participants.append(str(member.id))
        
        # Cancel pending leave
        if self.leave_task and not self.leave_task.done():
            self.leave_task.cancel()
            self.leave_task = None
            self.session.state = VoicePresenceState.CONNECTED
        
        # Auto-join if disconnected (and not manually left)
        if self.session.state == VoicePresenceState.DISCONNECTED:
            await self.join(channel)
        elif self.session.state == VoicePresenceState.MANUAL_LEFT:
            # Check policy for rejoining after manual leave
            if MANUAL_LEAVE_POLICY == "rejoin_after_empty":
                # Reset flag since someone joined
                self.session.manual_leave_flag = False
                await self.join(channel)
    
    async def _on_user_left(self, member: discord.Member, channel: discord.VoiceChannel):
        """Handle user leaving the target channel."""
        # Remove from participants
        if str(member.id) in self.session.participants:
            self.session.participants.remove(str(member.id))
        
        # Check if channel is now empty of non-bots
        non_bot_members = [m for m in channel.members if not m.bot]
        
        if len(non_bot_members) == 0 and self.is_connected:
            # Start cooldown before leaving
            self.session.state = VoicePresenceState.LEAVING_COOLDOWN
            self.leave_task = asyncio.create_task(self._delayed_leave())
    
    async def _delayed_leave(self):
        """Leave after cooldown if channel still empty."""
        try:
            await asyncio.sleep(EMPTY_CHANNEL_COOLDOWN_S)
            
            # Double-check channel is still empty
            channel = self.bot.get_channel(TARGET_VOICE_CHANNEL)
            if channel:
                non_bot_members = [m for m in channel.members if not m.bot]
                if len(non_bot_members) == 0:
                    await self.leave(reason="channel_empty")
        except asyncio.CancelledError:
            # Someone joined, cancel leave
            pass
    
    async def join(self, channel: discord.VoiceChannel) -> bool:
        """Join the voice channel."""
        try:
            if self.is_connected:
                return True
            
            # Use VoiceRecvClient for listening support
            cls = voice_recv.VoiceRecvClient if VOICE_RECV_AVAILABLE else None
            self.voice_client = await channel.connect(cls=cls)
            
            self.session.state = VoicePresenceState.CONNECTED
            self.session.connected_at = datetime.now()
            self.session.manual_leave_flag = False
            self.session.last_activity = datetime.now()
            
            print(f"🎤 Joined voice channel: {channel.name} (Recv: {VOICE_RECV_AVAILABLE})")
            await self._audit_log("voice.join", {"channel_id": channel.id})
            
            # Auto-enable listening (per user request)
            if VOICE_RECV_AVAILABLE:
                await self.toggle_listening(True)
            
            # Launch polite intro (DISABLED per user request to focus on text bot)
            # self.bot.loop.create_task(self._intro_sequence())
            
            return True
        except Exception as e:
            print(f"❌ Failed to join voice: {e}")
            return False

    async def _intro_sequence(self):
        """Introduce self immediately."""
        try:
            print("⏳ Intro: waiting (1s)...")
            await asyncio.sleep(1.0)
            
            # FORCE SPEAK (User request)
            text = (
                "Hello, I'm Mr Gagger. I'll just hang out here unless you need me. "
                "I am recording transcripts to enhance our relationship, but if you wish for me not to do that, "
                "please just say so and I'll leave."
            )
            print(f"🗣️ Speaking intro text: {text}")
            await self.speak(text)
        except Exception as e:
            print(f"⚠️ Intro sequence failed: {e}")
    
    def _setup_sink(self):
        """Setup audio sink."""
        if not self.voice_client:
            return
            
        self.sink = WhisperSink(self._on_transcript, self)
        self.voice_client.listen(self.sink)
        print("👂 Listening to voice channel...")

    async def leave(self, reason: str = "manual") -> bool:
        """Leave the voice channel."""
        try:
            if not self.is_connected:
                return True
            
            if self.sink:
                self.sink.cleanup()
                self.sink = None

            await self.voice_client.disconnect()
            self.voice_client = None
            
            if reason == "manual":
                self.session.state = VoicePresenceState.MANUAL_LEFT
                self.session.manual_leave_flag = True
            else:
                self.session.state = VoicePresenceState.DISCONNECTED
            
            self.session.disconnected_at = datetime.now()
            self.session.participants.clear()
            
            # Clear non-persistent transcripts
            if not self.session.logging_enabled:
                self.transcripts.clear()
            
            print(f"👋 Left voice channel (reason: {reason})")
            await self._audit_log("voice.leave", {"reason": reason})
            
            return True
        except Exception as e:
            print(f"❌ Failed to leave voice: {e}")
            return False
    
    async def toggle_listening(self, enabled: bool) -> bool:
        """Toggle voice transcription."""
        if enabled and not VOICE_RECV_AVAILABLE:
            print("⚠️ Cannot enable listening: discord-ext-voice-recv missing")
            return False
            
        self.session.listening_enabled = enabled
        
        if self.is_connected and isinstance(self.voice_client, voice_recv.VoiceRecvClient):
            if enabled:
                self.voice_client.listen(WhisperSink(self.add_transcript))
                print("👂 Started listening sink")
            else:
                self.voice_client.stop_listening()
                print("🙉 Stopped listening sink")
        
        await self._audit_log(
            "voice.stt_start" if enabled else "voice.stt_stop",
            {"channel_id": TARGET_VOICE_CHANNEL}
        )
        return True
    
    async def toggle_speaking(self, enabled: bool) -> bool:
        """Toggle TTS responses."""
        self.session.speaking_enabled = enabled
        return True
    
    def set_speaking_mode(self, mode: str) -> bool:
        """Set speaking mode: 'auto' or 'push_to_talk'."""
        if mode in ["auto", "push_to_talk"]:
            self.session.speaking_mode = mode
            return True
        return False
    
    def toggle_logging(self, enabled: bool) -> bool:
        """Toggle transcript persistence."""
        self.session.logging_enabled = enabled
        if not enabled:
            # Clear existing transcripts if turning off
            self.transcripts.clear()
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current voice status."""
        return {
            "connected": self.is_connected,
            "channel_id": TARGET_VOICE_CHANNEL,
            "state": self.session.state.value,
            "participants": self.session.participants,
            "listening": self.session.listening_enabled,
            "speaking": self.session.speaking_enabled,
            "speaking_mode": self.session.speaking_mode,
            "logging": self.session.logging_enabled,
            "connected_since": self.session.connected_at.isoformat() if self.session.connected_at else None
        }
    
    async def speak(self, text: str) -> bool:
        """Speak text via TTS (pausing listening)."""
        if not self.session.speaking_enabled:
            return False
        
        if not self.is_connected or not self.voice_client:
            return False
        
        # Check if someone is speaking (VAD)
        # Note: We skip this check for now to FORCE verify TTS works
        # if self.vad and not self.vad.should_bot_speak():
        #     await self._tts_queue.put(text)
        #     print(f"🔇 [TTS queued - user speaking] {text[:50]}...")
        #     return True
        
        if self.tts:
            try:
                # Pause listening to avoid Opus conflict
                was_listening = self.session.listening_enabled
                if was_listening:
                    print("🛑 Pausing listening for TTS...")
                    await self.toggle_listening(False)
                    await asyncio.sleep(0.2)
                
                # Speak (blocking)
                success = await self.tts.speak_in_channel(self.voice_client, text, wait=True)
                
                # Resume listening
                if was_listening:
                    print("👂 Resuming listening after TTS...")
                    await asyncio.sleep(0.2)
                    await self.toggle_listening(True)
                
                if success:
                    await self._audit_log("voice.tts_speak", {"text": text[:100]})
                    return True
                else:
                    print(f"⚠️ TTS playback failed, queuing: {text[:50]}...")
                    await self._tts_queue.put(text)
                    return False
            except Exception as e:
                print(f"❌ Failed to speak: {e}")
                # Ensure listening resumed
                if was_listening and not self.session.listening_enabled:
                    await self.toggle_listening(True)
                return False
        else:
            # Fallback: just log
            print(f"🔊 [TTS unavailable] {text}")
            await self._audit_log("voice.tts_speak", {"text": text[:100], "fallback": True})
            return True
    
    async def add_transcript(
        self,
        speaker_id: str,
        text: str,
        confidence: float = 0.9
    ):
        """Add a transcript event from STT."""
        from database import ProfileRepository
        
        # Map speaker to profile
        profile = ProfileRepository.get_by_discord_id(speaker_id)
        profile_id = profile.profile_id if profile else "unknown"
        
        event = TranscriptEvent(
            session_id=self.session.id,
            speaker_id=speaker_id,
            profile_id=profile_id,
            text=text,
            confidence=confidence,
            timestamp=datetime.now()
        )
        
        # Keep in memory
        self.transcripts.append(event)
        print(f"🗣️ [TRANSCRIPT] {speaker_id}: {text} ({confidence:.2f})")
        
        # Log to live transcript
        thought_logger.log("transcript", f"{profile_id}: {text}", {"speaker_id": speaker_id, "confidence": confidence})
        
        # If logging enabled, persist
        if self.session.logging_enabled:
            await self._persist_transcript(event)
        
        # Update mood from transcript
        await self._log_mood_from_transcript(event)
    
    async def _persist_transcript(self, event: TranscriptEvent):
        """Persist transcript to database."""
        from database import MessageRepository, MessageEvent
        
        # Create message event from transcript
        msg = MessageEvent(
            id=str(uuid.uuid4()),
            source="voice",
            channel_id=str(TARGET_VOICE_CHANNEL),
            user_id=event.speaker_id,
            content=event.text,
            timestamp=event.timestamp.isoformat(),
            profile_id=event.profile_id,
            inferred_mood=event.mood_signals
        )
        
        MessageRepository.insert(msg)
        print(f"💾 Persisted transcript for {event.speaker_id}")
    
    async def _log_mood_from_transcript(self, event: TranscriptEvent):
        """Extract mood signals from transcript."""
        from database import MoodRepository, MoodLog
        
        # Simple mood inference

        text_lower = event.text.lower()
        
        if any(w in text_lower for w in ["ugh", "fuck", "hate", "tired"]):
            tone = "stressed"
            intensity = 0.7
        elif any(w in text_lower for w in ["haha", "lol", "nice"]):
            tone = "playful"
            intensity = 0.6
        else:
            tone = "neutral"
            intensity = 0.5
        
        mood = MoodLog(
            id=str(uuid.uuid4()),
            profile_id=event.profile_id,
            timestamp=datetime.now().isoformat(),
            source="voice",
            signals={
                "tone": tone,
                "intensity": intensity,
                "confidence": 0.6
            },
            trigger_message_id=event.id
        )
        
        MoodRepository.insert(mood)
    
    async def _audit_log(self, tool: str, args: Dict[str, Any]):
        """Log voice actions to audit trail."""
        from pathlib import Path
        
        log_path = Path(os.path.dirname(os.path.abspath(__file__))) / "logs" / "tool_audit.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool,
            "args": args,
            "reason": "voice_worker",
            "result": {"success": True}
        }
        
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")


# ============================================================================
# Discord Bot Integration
# ============================================================================

class VoiceCog(commands.Cog):
    """Discord cog for voice commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.worker = VoiceWorker(bot)
    
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        await self.worker.handle_voice_state_update(member, before, after)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Check for active sessions on startup."""
        await self.worker.check_existing_sessions()

    @discord.app_commands.command(name="call")
    @discord.app_commands.describe(
        action="Action: join, leave, listen, speak, mode, log, status"
    )
    async def call_command(
        self,
        interaction: discord.Interaction,
        action: str,
        value: Optional[str] = None
    ):
        """Voice channel controls."""
        action = action.lower()
        
        if action == "join":
            channel = self.bot.get_channel(TARGET_VOICE_CHANNEL)
            if channel:
                success = await self.worker.join(channel)
                await interaction.response.send_message(
                    "🎤 Joined voice channel!" if success else "❌ Failed to join"
                )
            else:
                await interaction.response.send_message("❌ Channel not found")
        
        elif action == "leave":
            success = await self.worker.leave(reason="manual")
            await interaction.response.send_message(
                "👋 Left the call. Use `/call join` to rejoin." if success else "❌ Not connected"
            )
        
        elif action == "listen":
            enabled = value and value.lower() == "on"
            await self.worker.toggle_listening(enabled)
            status_msg = "ENABLED" if enabled else "DISABLED"
            detail = "I'll transcribe the call." if enabled else "Transcription stopped."
            await interaction.response.send_message(f"👂 Listening {status_msg}. {detail}")
        
        elif action == "speak":
            enabled = value and value.lower() == "on"
            await self.worker.toggle_speaking(enabled)
            status_msg = "ENABLED" if enabled else "DISABLED"
            detail = "I'll respond via voice." if enabled else "Voice responses stopped."
            await interaction.response.send_message(f"🔊 Speaking {status_msg}. {detail}")
        
        elif action == "mode":
            if value and value.lower() in ["auto", "push_to_talk"]:
                self.worker.set_speaking_mode(value.lower())
                detail = "I'll speak when relevant." if value.lower() == "auto" else "Use command to make me speak."
                await interaction.response.send_message(f"🎙️ Mode: {value.upper()}. {detail}")
            else:
                await interaction.response.send_message("❌ Mode must be 'auto' or 'push_to_talk'")
        
        elif action == "log":
            enabled = value and value.lower() == "on"
            self.worker.toggle_logging(enabled)
            await interaction.response.send_message(
                f"📝 Logging {'ON' if enabled else 'OFF'}. "
                f"{'Transcripts will be saved.' if enabled else 'Transcripts discarded after session.'}"
            )
        
        elif action == "status":
            status = self.worker.get_status()
            embed = discord.Embed(title="📊 Voice Status", color=discord.Color.blue())
            embed.add_field(name="Connected", value="✅" if status["connected"] else "❌", inline=True)
            embed.add_field(name="Listening", value="✅" if status["listening"] else "❌", inline=True)
            embed.add_field(name="Speaking", value="✅" if status["speaking"] else "❌", inline=True)
            embed.add_field(name="Mode", value=status["speaking_mode"], inline=True)
            embed.add_field(name="Logging", value="✅" if status["logging"] else "❌", inline=True)
            embed.add_field(name="Participants", value=len(status["participants"]), inline=True)
            await interaction.response.send_message(embed=embed)
        
        else:
            await interaction.response.send_message(
                "❌ Unknown action. Use: join, leave, listen, speak, mode, log, status"
            )


async def setup(bot: commands.Bot):
    """Add voice cog to bot."""
    await bot.add_cog(VoiceCog(bot))
