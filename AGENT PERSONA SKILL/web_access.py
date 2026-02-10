"""
Web Access Layer for Clawdbot
HTTP fetch, RSS parsing, and optional web search with caching and resilience.
"""
import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import urllib.request
    import ssl

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SKILL_DIR, "web_cache")
SOURCES_FILE = os.path.join(SKILL_DIR, "news_sources.json")

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

# Default timeouts
DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 3

# Default allowed/blocked domains
DEFAULT_ALLOWLIST = [
    "feeds.reuters.com",
    "rss.nytimes.com",
    "feeds.bbci.co.uk",
    "news.ycombinator.com",
    "feeds.arstechnica.com",
    "www.reddit.com",
    "techcrunch.com",
    "theverge.com"
]

DEFAULT_BLOCKLIST = [
    "malware.com",
    "phishing.example",
    "suspicious-downloads.net"
]

def _load_sources_config() -> Dict:
    """Load news sources configuration."""
    try:
        with open(SOURCES_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "feeds": [],
            "allowlist": DEFAULT_ALLOWLIST,
            "blocklist": DEFAULT_BLOCKLIST
        }

def _is_domain_allowed(url: str) -> bool:
    """Check if domain is allowed for fetching."""
    config = _load_sources_config()
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Check blocklist first
    for blocked in config.get("blocklist", DEFAULT_BLOCKLIST):
        if blocked.lower() in domain:
            return False
    
    # Always allow if in allowlist
    for allowed in config.get("allowlist", DEFAULT_ALLOWLIST):
        if allowed.lower() in domain:
            return True
    
    # Default: allow (but could be stricter)
    return True

def _get_cache_path(url: str) -> str:
    """Get cache file path for a URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{url_hash}.json")

def _get_cached(url: str, max_age_seconds: int = 300) -> Optional[Dict]:
    """Get cached response if still valid."""
    cache_path = _get_cache_path(url)
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
            cached_time = datetime.fromisoformat(cached["timestamp"])
            if datetime.now() - cached_time < timedelta(seconds=max_age_seconds):
                return cached["data"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    return None

def _set_cache(url: str, data: Any):
    """Cache response data."""
    cache_path = _get_cache_path(url)
    cached = {
        "timestamp": datetime.now().isoformat(),
        "url": url,
        "data": data
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cached, f)

def web_fetch(
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    cache_seconds: int = 300,
    headers: Dict = None
) -> Optional[str]:
    """
    Fetch content from a URL with retries and caching.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        retries: Number of retry attempts
        cache_seconds: How long to cache the response (0 to disable)
        headers: Optional custom headers
    
    Returns:
        Response text or None on failure
    """
    # Check domain policy
    if not _is_domain_allowed(url):
        print(f"[WebAccess] Domain blocked: {url}")
        return None
    
    # Check cache
    if cache_seconds > 0:
        cached = _get_cached(url, cache_seconds)
        if cached:
            return cached
    
    # Fetch with retries
    default_headers = {
        "User-Agent": "Clawdbot/1.0 (Windows; AI Agent)"
    }
    if headers:
        default_headers.update(headers)
    
    for attempt in range(retries):
        try:
            if HTTPX_AVAILABLE:
                with httpx.Client(timeout=timeout) as client:
                    response = client.get(url, headers=default_headers)
                    response.raise_for_status()
                    text = response.text
            else:
                # Fallback to urllib
                ctx = ssl.create_default_context()
                req = urllib.request.Request(url, headers=default_headers)
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                    text = response.read().decode("utf-8")
            
            # Cache successful response
            if cache_seconds > 0:
                _set_cache(url, text)
            
            return text
            
        except Exception as e:
            wait_time = (2 ** attempt) + (time.time() % 1)  # Exponential backoff with jitter
            print(f"[WebAccess] Fetch attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(wait_time)
    
    return None

def rss_fetch(feed_url: str) -> List[Dict]:
    """
    Fetch and parse an RSS feed.
    
    Returns list of items with: title, link, published, summary
    """
    content = web_fetch(feed_url, cache_seconds=600)  # Cache RSS for 10 minutes
    if not content:
        return []
    
    items = []
    try:
        root = ET.fromstring(content)
        
        # Handle both RSS and Atom feeds
        if root.tag == "rss":
            # RSS 2.0
            for item in root.findall(".//item"):
                items.append({
                    "title": _get_text(item, "title"),
                    "link": _get_text(item, "link"),
                    "published": _get_text(item, "pubDate"),
                    "summary": _get_text(item, "description")[:300] if _get_text(item, "description") else ""
                })
        elif "feed" in root.tag.lower() or "atom" in root.tag.lower():
            # Atom
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//atom:entry", ns) or root.findall(".//entry"):
                link = ""
                link_elem = entry.find("atom:link", ns) or entry.find("link")
                if link_elem is not None:
                    link = link_elem.get("href", link_elem.text or "")
                
                items.append({
                    "title": _get_text(entry, "atom:title", ns) or _get_text(entry, "title"),
                    "link": link,
                    "published": _get_text(entry, "atom:published", ns) or _get_text(entry, "published") or _get_text(entry, "updated"),
                    "summary": (_get_text(entry, "atom:summary", ns) or _get_text(entry, "summary") or "")[:300]
                })
        else:
            # Try generic item parsing
            for item in root.iter():
                if item.tag in ["item", "entry"]:
                    items.append({
                        "title": _get_text(item, "title"),
                        "link": _get_text(item, "link"),
                        "published": _get_text(item, "pubDate") or _get_text(item, "published"),
                        "summary": (_get_text(item, "description") or _get_text(item, "summary") or "")[:300]
                    })
    
    except ET.ParseError as e:
        print(f"[WebAccess] RSS parse error: {e}")
    
    return items

def _get_text(element: ET.Element, tag: str, namespaces: Dict = None) -> str:
    """Helper to get text from an XML element."""
    if namespaces:
        child = element.find(tag, namespaces)
    else:
        child = element.find(tag)
    
    if child is not None and child.text:
        return child.text.strip()
    return ""

# Simple TTL cache (prevents spamming providers on retries)
_search_cache: Dict[str, Dict] = {}
_SEARCH_CACHE_TTL_SEC = 60 * 10

def _cache_get(key: str):
    v = _search_cache.get(key)
    if not v:
        return None
    if (time.time() - v["ts"]) > _SEARCH_CACHE_TTL_SEC:
        _search_cache.pop(key, None)
        return None
    return v["data"]

def _cache_set(key: str, data):
    _search_cache[key] = {"ts": time.time(), "data": data}

def search_web(query: str, max_results: int = 5, *, timelimit: Optional[str] = None) -> List[Dict]:
    """
    Returns: [{title, url, snippet, source}]
    Backends:
      1) Brave Search API if BRAVE_SEARCH_API_KEY is set
      2) DuckDuckGo (no-key) fallback
    """
    q = (query or "").strip()
    if not q:
        return []

    cache_key = f"q={q}|n={max_results}|t={timelimit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # 1) Brave Search API (reliable, but needs key)
    brave_key = os.environ.get("BRAVE_SEARCH_API_KEY") or os.environ.get("BRAVE_API_KEY")
    if brave_key:
        try:
            import requests
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": brave_key,
            }
            params = {"q": q, "count": min(int(max_results), 20), "offset": 0}
            r = requests.get("https://api.search.brave.com/res/v1/web/search", headers=headers, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            out = []
            for item in (data.get("web", {}) or {}).get("results", [])[:max_results]:
                out.append({
                    "title": item.get("title", "").strip(),
                    "url": item.get("url", "").strip(),
                    "snippet": (item.get("description") or "").strip(),
                    "source": "brave",
                })
            if out:
                _cache_set(cache_key, out)
                return out
        except Exception as e:
            print(f"[WebAccess] Brave Search failed: {e}")

    # 2) Fallback to DuckDuckGo Instant Answer (already implementation in web_search original)
    # Or use the DDGS library if available. Let's try to keep it minimal but robust.
    # I'll keep the basic web_search logic as a fallback.
    
    ddg_url = f"https://api.duckduckgo.com/?q={q}&format=json&no_redirect=1"
    content = web_fetch(ddg_url, cache_seconds=60)
    if not content:
        return []
    
    results = []
    try:
        data = json.loads(content)
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", "Result"),
                "url": data.get("AbstractURL", ""),
                "snippet": data.get("Abstract", ""),
                "source": "ddg_instant"
            })
        for topic in data.get("RelatedTopics", [])[:max_results - 1]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                    "source": "ddg_instant"
                })
    except: pass
    
    if results:
        _cache_set(cache_key, results)
    return results[:max_results]

# Aliases for compatibility
web_search = search_web
search = search_web

def extract_links_from_text(text: str, max_links: int = 3) -> List[str]:
    """
    Extract URLs from text content.
    Used to include source links in responses.
    """
    import re
    url_pattern = r'https?://[^\s<>"\']+[^\s<>"\'.,;:!?\)]'
    urls = re.findall(url_pattern, text)
    return list(set(urls))[:max_links]

def format_links_for_response(links: List[str]) -> str:
    """Format links for inclusion in a response."""
    if not links:
        return ""
    
    formatted = []
    for i, link in enumerate(links[:3], 1):
        # Try to extract domain for display
        parsed = urlparse(link)
        domain = parsed.netloc.replace("www.", "")
        formatted.append(f"[{domain}]({link})")
    
    return " | ".join(formatted)

class WebAccessLayer:
    """
    Unified web access with policy enforcement and caching.
    """
    
    def __init__(self):
        self.config = _load_sources_config()
        self.last_fetch_times = {}  # Rate limiting per domain
    
    def fetch(self, url: str, **kwargs) -> Optional[str]:
        """Fetch URL content with policy checks."""
        return web_fetch(url, **kwargs)
    
    def rss(self, feed_url: str) -> List[Dict]:
        """Fetch and parse RSS feed."""
        return rss_fetch(feed_url)
    
    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Perform web search."""
        return web_search(query, max_results)
    
    def get_with_links(self, url: str) -> Dict:
        """
        Fetch content and extract any links from it.
        Returns: {"content": str, "links": List[str]}
        """
        content = self.fetch(url)
        if not content:
            return {"content": "", "links": []}
        
        links = extract_links_from_text(content)
        return {"content": content, "links": links}

# Global instance
web_access = WebAccessLayer()

if __name__ == "__main__":
    # Test
    print("Testing Web Access Layer...")
    
    # Test RSS fetch
    print("\n📰 Fetching HN RSS...")
    items = rss_fetch("https://news.ycombinator.com/rss")
    print(f"Got {len(items)} items")
    if items:
        print(f"First item: {items[0]['title'][:50]}...")
    
    # Test web search
    print("\n🔍 Testing search...")
    results = web_search("python programming", max_results=3)
    print(f"Got {len(results)} results")
    for r in results:
        print(f"  - {r['title'][:50]}")
    
    # Test link formatting
    links = ["https://news.ycombinator.com", "https://python.org"]
    print(f"\n🔗 Formatted links: {format_links_for_response(links)}")
