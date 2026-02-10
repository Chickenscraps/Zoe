"""
VAD Filter using webrtcvad
Proper Voice Activity Detection for robust speech detection.
Based on AGI Architecture Upgrade research §5.
"""
import webrtcvad
from typing import Optional
from collections import deque

class VADFilter:
    """
    Voice Activity Detection filter using webrtcvad.
    Buffers speech and returns complete utterances on silence.
    """
    
    def __init__(self, aggressiveness: int = 2, sample_rate: int = 48000):
        """
        Args:
            aggressiveness: 0-3, higher = more aggressive filtering (less false positives)
            sample_rate: Audio sample rate (Discord uses 48000)
        """
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        
        # Buffer for accumulating speech frames
        self.speech_buffer = bytearray()
        
        # Ring buffer for detecting silence (last N frames)
        self.ring_buffer = deque(maxlen=10)  # ~300ms at 30ms frames
        
        # State
        self.triggered = False
        self.silence_frames = 0
        self.silence_threshold = 15  # ~450ms of silence to end utterance
        
    def is_speech(self, pcm_chunk: bytes) -> bool:
        """
        Check if a PCM chunk contains speech.
        
        Args:
            pcm_chunk: Raw PCM audio bytes (16-bit, mono)
            
        Returns:
            True if speech detected
        """
        # webrtcvad requires specific frame sizes: 10, 20, or 30 ms
        # At 48kHz, 30ms = 1440 samples = 2880 bytes (16-bit)
        frame_size = int(self.sample_rate * 0.03 * 2)  # 30ms frame in bytes
        
        if len(pcm_chunk) < frame_size:
            return False
            
        # Take first frame_size bytes
        frame = pcm_chunk[:frame_size]
        
        try:
            return self.vad.is_speech(frame, self.sample_rate)
        except Exception:
            return False
    
    def process(self, pcm_chunk: bytes) -> Optional[bytes]:
        """
        Process PCM audio and return complete utterance when detected.
        
        Args:
            pcm_chunk: Raw PCM audio bytes
            
        Returns:
            Complete speech buffer when silence detected, None otherwise
        """
        is_speech = self.is_speech(pcm_chunk)
        self.ring_buffer.append(is_speech)
        
        if not self.triggered:
            # Not currently in speech - look for speech start
            num_voiced = sum(self.ring_buffer)
            if num_voiced > 0.8 * len(self.ring_buffer):
                # Speech detected - start buffering
                self.triggered = True
                self.speech_buffer.extend(pcm_chunk)
                self.silence_frames = 0
        else:
            # Currently in speech - buffer and check for end
            self.speech_buffer.extend(pcm_chunk)
            
            if not is_speech:
                self.silence_frames += 1
            else:
                self.silence_frames = 0
            
            # Check if we've hit silence threshold
            if self.silence_frames >= self.silence_threshold:
                # Utterance complete
                result = bytes(self.speech_buffer)
                self.reset()
                return result
        
        return None
    
    def reset(self):
        """Reset the filter state."""
        self.speech_buffer.clear()
        self.ring_buffer.clear()
        self.triggered = False
        self.silence_frames = 0
    
    def is_active(self) -> bool:
        """Check if currently buffering speech."""
        return self.triggered


# Convenience function for simple speech check
def is_speech_simple(pcm_data: bytes, sample_rate: int = 48000, aggressiveness: int = 2) -> bool:
    """Simple one-shot speech detection."""
    vad = webrtcvad.Vad(aggressiveness)
    frame_size = int(sample_rate * 0.03 * 2)
    
    if len(pcm_data) < frame_size:
        return False
    
    try:
        return vad.is_speech(pcm_data[:frame_size], sample_rate)
    except Exception:
        return False
