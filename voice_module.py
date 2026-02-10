import os
import asyncio
import edge_tts
from pathlib import Path

class VoiceModule:
    """
    Zoe's Voice Module using Edge-TTS (free, high quality).
    """
    def __init__(self):
        # Voice selection: 
        # en-US-AnaNeural (Child/Teen female) - Good for "bratty/playful"
        # en-US-AvaNeural (Young adult female) - Professional yet soft
        # en-US-EmmaNeural (Young adult female) - Standard helpful AI
        # en-US-JennyNeural (Young adult female) - Very standard
        
        # We want "Cool/Casual/Slightly deep" -> Ava or maybe a UK voice?
        # Let's stick with Ava for now, or maybe an Aussie accent?
        # en-AU-NatashaNeural (Australian) - Could be fun?
        
        # Let's go with "Ava" (Multitasker) or "Michelle"
        self.voice = "en-US-AvaNeural" 
        self.output_dir = Path("temp_audio")
        self.output_dir.mkdir(exist_ok=True)
        
    async def generate_speech(self, text: str, filename: str = "speech.mp3") -> str:
        """
        Generate MP3 from text.
        Returns the absolute path to the file.
        """
        output_path = self.output_dir / filename
        
        # Rate: +0% is default. +10% is faster.
        # Pitch: +0Hz is default. -5Hz is deeper.
        communicate = edge_tts.Communicate(text, self.voice, rate="+0%", pitch="-2Hz")
        
        await communicate.save(str(output_path))
        return str(output_path.absolute())

    async def list_voices(self):
        """Debug tool to find the perfect voice."""
        voices = await edge_tts.list_voices()
        for v in voices:
            if "en-" in v["ShortName"] and "Neural" in v["ShortName"]:
                print(f"{v['ShortName']} - {v['Gender']}")

if __name__ == "__main__":
    # Test
    async def test():
        vm = VoiceModule()
        path = await vm.generate_speech("Hey Josh, I just deployed a new app. Check general chat.")
        print(f"Generated: {path}")
        # os.system(f"start {path}") # Play it
        
    asyncio.run(test())
