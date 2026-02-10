"""
Layer A Tools: Web Automation (Browser Control)
Uses Playwright to give Zoe direct browser capabilities.
"""
import os
import json
import logging
from typing import Dict, Any, Optional

# Global browser state
_BROWSER = None
_CONTEXT = None
_PAGE = None

logger = logging.getLogger(__name__)

def _get_page(headless: bool = False):
    """Ensure a browser page exists, launching if necessary."""
    global _BROWSER, _CONTEXT, _PAGE
    
    try:
        from playwright.sync_api import sync_playwright
        
        if _PAGE and not _PAGE.is_closed():
            return _PAGE

        if not _BROWSER:
            # We need to keep the playwright object alive too, but sync_playwright context manager closes it?
            # We'll use the 'start()' method if possible, or keep the context manager in a global thread/loop?
            # For a simple tool call structure, we might need to re-launch every time OR use a persistent server.
            # Re-launching is slow.
            # Better approach for a stateless bot: 
            # 1. Check if we can attach to an existing Chrome instance debugging port?
            # 2. Or just accept re-launch for V1.
            # Let's try to keep it alive in global scope (might be flaky across restarts).
            
            # Use sync_playwright().start() pattern for persistent global
            p = sync_playwright().start()
            _BROWSER = p.chromium.launch(headless=headless)
            _CONTEXT = _BROWSER.new_context()
            _PAGE = _CONTEXT.new_page()
            
        elif _CONTEXT and not _PAGE:
             _PAGE = _CONTEXT.new_page()
             
        return _PAGE
        
    except Exception as e:
        logger.error(f"Failed to launch browser: {e}")
        return None

def launch_browser(headless: bool = False, url: Optional[str] = None) -> str:
    """Explicitly launch the browser."""
    page = _get_page(headless)
    if not page:
        return "❌ Failed to launch browser."
    
    if url:
        try:
            page.goto(url)
            return f"✅ Launched browser and navigated to {url}"
        except Exception as e:
            return f"✅ Launched browser, but failed to nav: {e}"
            
    return "✅ Browser launched and ready."

def browser_navigate(url: str) -> str:
    """Navigate current page to a URL."""
    page = _get_page(headless=False) # Default to visible for Layer A
    if not page: return "❌ Browser not available."
    
    try:
        page.goto(url)
        return f"✅ Navigated to {url}"
    except Exception as e:
        return f"❌ Navigation failed: {e}"

def browser_click(selector: str, wait_ms: int = 1000) -> str:
    """Click an element on the page."""
    page = _get_page()
    if not page: return "❌ Browser not available."
    
    try:
        # Try to click
        page.click(selector, timeout=5000)
        page.wait_for_timeout(wait_ms)
        return f"✅ Clicked '{selector}'"
    except Exception as e:
        return f"❌ Click failed for '{selector}': {e}"

def browser_type(selector: str, text: str) -> str:
    """Type text into an element."""
    page = _get_page()
    if not page: return "❌ Browser not available."
    
    try:
        page.fill(selector, text)
        return f"✅ Typed '{text}' into '{selector}'"
    except Exception as e:
        return f"❌ Typing failed: {e}"

def browser_snapshot() -> str:
    """
    Returns a 'Semantic Snapshot' of the page for the LLM to understand structure.
    Also takes a visual screenshot for the user.
    """
    page = _get_page()
    if not page: return "❌ Browser not available."
    
    try:
        # 1. Visual Screenshot
        import time
        filename = f"browser_snap_{int(time.time())}.png"
        path = os.path.join(os.getcwd(), "temp_vision", filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        page.screenshot(path=path)
        
        # 2. Semantic Snapshot (Simplified HTML or Accessibility Tree)
        # We'll grab the title and a simplified dump of interactive elements
        title = page.title()
        url = page.url
        
        # Extract links and inputs via JS
        # This is a key part of "Blind Web Agent" logic
        js_script = """
        () => {
            const elements = document.querySelectorAll('a, button, input, select, textarea');
            return Array.from(elements).map(el => {
                let text = el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '';
                text = text.replace(/\\s+/g, ' ').trim().substring(0, 50);
                
                // unique selector logic (simplified)
                let selector = el.tagName.toLowerCase();
                if (el.id) selector += '#' + el.id;
                else if (el.className) selector += '.' + el.className.split(' ').join('.');
                
                return `[${el.tagName.toLowerCase()}] ${text} (selector: ${selector})`;
            }).filter(s => s.length > 10).slice(0, 50); // Limit to top 50 
        }
        """
        interactive_schema = page.evaluate(js_script)
        
        snapshot_text = f"🌐 **Page: {title}**\nURL: {url}\n\n**Interactive Elements (Top 50):**\n"
        snapshot_text += "\n".join(interactive_schema)
        snapshot_text += f"\n\n📸 Visual Snapshot saved to: {path}"
        
        return snapshot_text
        
    except Exception as e:
        return f"❌ Snapshot failed: {e}"
