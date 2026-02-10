"""
Transcription Service for Clawdbot
Uses faster-whisper to transcribe audio from voice channels
"""
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict

try:
    from faster_whisper import WhisperModel
    import torch
    WHISPER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Whisper import failed: {e}")
    WHISPER_AVAILABLE = False

# ============================================================================
# Configuration
# ============================================================================

MODEL_SIZE = "base"  # base, small, medium, large-v3
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("transcription")

class TranscriptionService:
    """Handles audio transcription using faster-whisper."""
    
    def __init__(self):
        self.model = None
        self.initialized = False
        
        if WHISPER_AVAILABLE:
            logger.info(f"🎙️ Whisper Service initialized (Device: {DEVICE})")
        else:
            logger.warning("⚠️ Whisper Service unavailable (missing dependencies)")
    
    def _load_model(self):
        """Lazy load the Whisper model."""
        if self.model:
            return
        
        if not WHISPER_AVAILABLE:
            raise RuntimeError("Whisper dependencies not met")
            
        logger.info(f"⏳ Loading Whisper model '{MODEL_SIZE}' on {DEVICE}...")
        try:
            self.model = WhisperModel(
                MODEL_SIZE, 
                device=DEVICE, 
                compute_type=COMPUTE_TYPE
            )
            self.initialized = True
            logger.info("✅ Whisper model loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load Whisper model: {e}")
            raise

    async def transcribe_file(self, file_path: str) -> Dict[str, str]:
        """
        Transcribe an audio file.
        
        Args:
            file_path: Path to the audio file (wav/mp3/pcm)
            
        Returns:
            Dict containing 'text', 'language', 'confidence'
        """
        if not WHISPER_AVAILABLE:
            return {"text": "", "error": "Whisper unavailable"}
            
        if not os.path.exists(file_path):
            return {"text": "", "error": "File not found"}

        # Offload blocking model call to thread
        return await asyncio.to_thread(self._transcribe_sync, file_path)

    def _transcribe_sync(self, file_path: str) -> Dict[str, str]:
        """Synchronous transcription (runs in thread)."""
        try:
            self._load_model()
            
            segments, info = self.model.transcribe(
                file_path, 
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            # Collect all text
            text = " ".join([segment.text for segment in segments]).strip()
            
            return {
                "text": text,
                "language": info.language,
                "confidence": info.language_probability
            }
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            return {"text": "", "error": str(e)}

# Global instance
transcription_service = TranscriptionService()
