
import os
import sys
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Setup paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from tts_service import TTSService
from voice_worker import WhisperSink, VoiceWorker

def test_tts_config():
    print("\n🧪 Testing TTS Configuration...")
    service = TTSService()
    print(f"   Voice: {service.voice}")
    assert "Jenny" in service.voice
    print("✅ Voice is set to Jenny (Female US).")

async def test_interruption_logic():
    print("\n🧪 Testing Interruption Logic...")
    
    # Mock TTS and Voice Client
    mock_vc = MagicMock()
    mock_vc.is_playing.return_value = True
    
    service = TTSService()
    
    # Simulate speaking
    service._is_speaking = True
    
    # Test stop_speaking
    service.stop_speaking(mock_vc)
    
    assert service.is_speaking is False
    mock_vc.stop.assert_called_once()
    print("✅ stop_speaking() correctly stops voice client.")

async def test_vad_sink():
    print("\n🧪 Testing VAD Interruption...")
    
    # Mock Worker
    mock_worker = MagicMock()
    mock_worker.is_speaking = True
    
    sink = WhisperSink(callback=None, voice_worker=mock_worker)
    
    # Mock Packet
    mock_packet = MagicMock()
    mock_packet.user.name = "TestUser"
    mock_packet.user.id = 123
    
    # Generate Loud Static (Random bytes)
    import random
    loud_data = bytes([random.getrandbits(8) for _ in range(3840)]) # 20ms of audio
    # Mock the .pcm attribute which voice_recv provided
    mock_data_obj = MagicMock()
    mock_data_obj.pcm = loud_data
    mock_packet.data = mock_data_obj
    
    # Write loud data
    sink.write(mock_packet.user, mock_data_obj)
    
    # Verify interrupt called
    # Note: RMS of random bytes might not always exceed 200 depending on randomness,
    # but likely will for byte values 0-255 centered around 128?
    # actually audioop.rms expects signed 16-bit.
    # Let's craft specific loud data.
    # Max amplitude 16-bit is 32767. 
    # \xff\7f is approx max positive.
    loud_pcm = b'\xff\x7f' * 1920 # ~32000 value
    mock_data_obj.pcm = loud_pcm
    
    sink.write(mock_packet.user, mock_data_obj)
    
    mock_worker.interrupt.assert_called()
    print("✅ VAD detected loud audio and triggered interrupt.")

if __name__ == "__main__":
    test_tts_config()
    asyncio.run(test_interruption_logic())
    asyncio.run(test_vad_sink())
