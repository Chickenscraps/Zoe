import asyncio
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Add CWD to sys.path
sys.path.append(os.getcwd())

async def test_engagement_pipeline():
    print("Testing Zoe Engagement Pipeline...")
    
    # 1. Test Captions
    print("\n--- Testing Captions ---")
    from media_utils import CaptionGenerator
    cap = CaptionGenerator.get_caption("TRADE_OPEN")
    print(f"Caption (Open): {cap}")
    assert any(cap in t for t in CaptionGenerator.TEMPLATES["TRADE_OPEN"])

    # 2. Test GIF Picker (Mocked API)
    print("\n--- Testing GIF Picker ---")
    with patch("media_utils.GifPicker.API_KEY", "fake_key"):
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            async def mock_json():
                return {"results": [{"media_formats": {"gif": {"url": "https://test.gif"}}}]}
            mock_resp.json = mock_json
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            from media_utils import gif_picker
            gif = await gif_picker.get_gif("TRADE_CLOSE_GREEN")
            print(f"GIF URL: {gif}")
            assert gif == "https://test.gif"

    # 3. Test Renderer Mock
    print("\n--- Testing Renderer Flow ---")
    from renderer import renderer
    with patch.object(renderer, "render", new_callable=AsyncMock) as mock_render:
        mock_render.return_value = b"fake_png_bytes"
        
        with patch.object(renderer, "upload_to_supabase", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "https://supabase.com/artifact.png"
            
            # Setup Mock Bot and Engagement Engine
            mock_bot = MagicMock()
            mock_channel = AsyncMock()
            mock_bot.get_channel.return_value = mock_channel
            
            from clawdbot import EngagementEngine
            ee = EngagementEngine(mock_bot)
            
            # Mock supabase_memory
            with patch("supabase_memory.supabase_memory") as mock_db:
                mock_db.initialized = True
                
                print("Running post_trade_event...")
                await ee.post_trade_event(
                    event_type="TRADE_OPEN",
                    trade_id="t123",
                    symbol="NVDA",
                    details={"side": "buy", "qty": 1, "price": 100.0}
                )
                
                # Verify Discord channel received a message
                mock_channel.send.assert_called()
                print("Done Discord message sent (mocked)")

    print("\nVerification Complete: Engagement Pipeline is ready for launch.")

if __name__ == "__main__":
    asyncio.run(test_engagement_pipeline())
