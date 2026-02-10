---
name: clawdbot-integration
description: Integration with Google APIs (Weather, Maps, Gmail, etc.) for Clawdbot assistant
---

# Clawdbot Integration Skill

This skill configures the agent to use Google APIs for environmental data, mapping, productivity, and communication tasks.

---
## 🔧 Configuration
- **API Credentials:** Load all API keys from environment variables via `python-dotenv` or secure `.env` management.
- **Secure Handling:** Use `GOOGLE_APPLICATION_CREDENTIALS` for service account-based APIs.
- **Authentication:** Apply OAuth 2.0 for user-scope APIs (Gmail, Calendar, Drive, etc.) with limited scopes.

---
## 🧠 Tool Wrappers & Logic

### 🗺️ Maps & Navigation APIs
```python
# maps_tools.py
import googlemaps, os

gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))

def get_directions(origin, destination):
    return gmaps.directions(origin, destination)

def geocode(location):
    return gmaps.geocode(location)

def get_elevation(lat, lon):
    return gmaps.elevation((lat, lon))
```

### 🌍 Environmental APIs
```python
# environment_tools.py
import requests, os

ENV_KEY = os.getenv("GOOGLE_ENV_API_KEY")

BASE = "https://airquality.googleapis.com/v1"

def get_air_quality(lat, lon):
    url = f"{BASE}/currentConditions:lookup?key={ENV_KEY}"
    return requests.post(url, json={"location": {"latitude": lat, "longitude": lon}}).json()
```

### 📧 Gmail / 📆 Calendar / 📁 Drive APIs
```python
# productivity_tools.py
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

def get_gmail_service(creds):
    return build('gmail', 'v1', credentials=creds)

def get_calendar_service(creds):
    return build('calendar', 'v3', credentials=creds)
```

---
## 🗂️ Folder Layout
```
/.agent/skills/clawdbot-integration/
│
├── SKILL.md
├── .env.example
├── maps_tools.py
├── environment_tools.py
├── productivity_tools.py
├── vision_tools.py
├── youtube_tools.py
├── auth/
│   └── oauth_init.py
├── clawdbot.log
└── __init__.py
```

---
## 🔐 Permissions & Scopes
- Use OAuth scopes such as `calendar.readonly`, `gmail.send`, `drive.readonly`, etc.
- Never request more than needed.
- Log user confirmation before write/send actions.

---
## 🔁 Routing Rules
| Query Type                     | API Tool Called                   |
|-------------------------------|------------------------------------|
| "air quality"                 | `get_air_quality(lat, lon)`       |
| "map directions"             | `get_directions()`                |
| "send email"                 | `gmail_client.messages().send()` |
| "translate this"             | Translation API                    |
| "analyze this screenshot"    | Vision API                         |
| "what’s on my calendar"      | Calendar API                       |

---
## 📝 Logging
```python
# logger.py
from datetime import datetime

def log_action(tool, params, status, output=None):
    with open("clawdbot.log", "a") as f:
        f.write(f"[{datetime.now()}] {tool} {params} -> {status}\n")
```

---
## ✅ Examples
- "What's the pollen count today?" → `get_pollen_forecast()`
- "Route from home to gym" → `get_directions('my address', 'gym')`
- "Remind me to stretch at 9am" → Calendar API
- "Email John my workout log" → Gmail + Drive API

---
## 🚨 Error Handling & Fallbacks
- Catch all `requests` or `client` errors
- Retry once on rate limit
- Use fallback message: "That tool is temporarily unavailable."
- All errors logged via `log_action()`

---
## 🗣️ Voice Support
- If user sends audio:
    1. Use Speech-to-Text to transcribe
    2. Use original logic for task detection
    3. Speak back via Text-to-Speech (if enabled)

---
## 🧪 .env.example
```
GOOGLE_MAPS_API_KEY=your_maps_key
GOOGLE_ENV_API_KEY=your_environmental_key
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

---
## 📦 Day 1 Setup Script
```bash
pip install -r requirements.txt
python auth/oauth_init.py  # for user-scoped APIs
python app.py
```

---
## 📈 Expansion Plan
- Add YouTube data wrapper
- Add YouTube transcript indexing
- Add vector store integration (for RAG)
- Add tool introspection for self-validation

---
Ready to activate this skill and route queries to all Clawdbot API tools.

> For full documentation and rationale, refer to:
> `C:\Users\josha\OneDrive\Desktop\Clawd\research\On-Device Dual-Mode Agent System Plan.md`

