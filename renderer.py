import os
import asyncio
import logging
import time
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class DashboardRenderer:
    """Renders Dashboard Share Routes to PNG using Playwright."""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("DASHBOARD_BASE_URL", "http://localhost:5173")
        self.browser = None
        self.context = None
        self._lock = asyncio.Lock()
        
    async def start(self):
        """Start the browser instance."""
        async with self._lock:
            if not self.browser:
                pw = await async_playwright().start()
                self.browser = await pw.chromium.launch(headless=True)
                self.context = await self.browser.new_context(
                    viewport={'width': 1280, 'height': 720}
                )
                logger.info(f"🚀 Dashboard Renderer started at {self.base_url}")

    async def stop(self):
        """Stop the browser."""
        if self.browser:
            await self.browser.close()
            self.browser = None
            logger.info("🛑 Dashboard Renderer stopped")

    async def render(self, kind: str, target_id: str = None) -> Optional[bytes]:
        """
        Render a specific share route to PNG.
        
        Args:
            kind: 'trade', 'position', 'pnl'
            target_id: ID of the record if relevant
            
        Returns:
            PNG bytes or None if failed
        """
        if not self.browser:
            await self.start()
            
        url = f"{self.base_url}/share/{kind}"
        if target_id:
            url += f"/{target_id}"
        
        # Add cache buster and theme
        url += "?theme=dark&compact=1&hide=nav"
        
        selector = f'[data-testid="{kind}-ticket"]'
        if kind == 'pnl': selector = '[data-testid="pnl-summary"]'
        
        page = await self.context.new_page()
        try:
            logger.info(f"📸 Rendering {url} ...")
            await page.goto(url, wait_until="networkidle", timeout=15000)
            
            # Wait for specific card selector
            element = await page.wait_for_selector(selector, timeout=10000)
            if not element:
                logger.error(f"❌ Element {selector} not found on {url}")
                return None
                
            # Take screenshot of JUST the card
            screenshot = await element.screenshot(type="png")
            return screenshot
            
        except Exception as e:
            logger.error(f"❌ Rendering failed for {url}: {e}")
            return None
        finally:
            await page.close()

    async def upload_to_supabase(self, png_bytes: bytes, filename: str) -> Optional[str]:
        """Upload to Supabase Storage and return public URL."""
        try:
            from supabase_memory import supabase_memory
            if not supabase_memory or not supabase_memory.client:
                return None
            
            # Upload to 'artifacts' bucket
            bucket = "artifacts"
            content_type = "image/png"
            
            # Supabase Python SDK upload
            res = supabase_memory.client.storage.from_(bucket).upload(
                path=filename,
                file=png_bytes,
                file_options={"content-type": content_type, "x-upsert": "true"}
            )
            
            # Get Public URL
            url = supabase_memory.client.storage.from_(bucket).get_public_url(filename)
            return url
            
        except Exception as e:
            logger.error(f"❌ Supabase upload failed: {e}")
            return None

# Singleton instance
renderer = DashboardRenderer()
