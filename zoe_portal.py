"""
Zoe's Creative Portal
Flask web app to showcase Zoe's autonomous creations.
"""
import os
import json
from pathlib import Path
from flask import Flask, render_template_string, send_from_directory, abort

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
PROJECTS_DIR = PROJECT_ROOT / "zoe_projects"
PORT = 5050

# Ensure projects directory exists
PROJECTS_DIR.mkdir(exist_ok=True)

# ============================================================================
# Flask App
# ============================================================================

app = Flask(__name__)

# ============================================================================
# Templates
# ============================================================================

GALLERY_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zoe's Creations 💜</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #eee;
            padding: 40px 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 50px;
        }
        
        h1 {
            font-size: 3rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .subtitle {
            color: #888;
            font-size: 1.1rem;
        }
        
        .projects-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
        }
        
        .project-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 25px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all 0.3s ease;
            text-decoration: none;
            color: inherit;
            display: block;
        }
        
        .project-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(102, 126, 234, 0.5);
        }
        
        .project-type {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            margin-bottom: 15px;
        }
        
        .type-game {
            background: rgba(255, 107, 107, 0.2);
            color: #ff6b6b;
        }
        
        .type-tool {
            background: rgba(78, 205, 196, 0.2);
            color: #4ecdc4;
        }
        
        .type-art {
            background: rgba(167, 139, 250, 0.2);
            color: #a78bfa;
        }
        
        .project-name {
            font-size: 1.4rem;
            font-weight: 600;
            margin-bottom: 10px;
        }
        
        .project-desc {
            color: #aaa;
            font-size: 0.95rem;
            line-height: 1.5;
        }
        
        .project-date {
            margin-top: 15px;
            font-size: 0.8rem;
            color: #666;
        }
        
        .empty-state {
            text-align: center;
            padding: 80px 20px;
            color: #666;
        }
        
        .empty-state h2 {
            font-size: 1.5rem;
            margin-bottom: 15px;
        }
        
        footer {
            text-align: center;
            margin-top: 60px;
            color: #555;
            font-size: 0.9rem;
        }
        
        .stats {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 30px;
        }
        
        .stat {
            text-align: center;
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: #667eea;
        }
        
        .stat-label {
            color: #888;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Zoe's Creations 💜</h1>
            <p class="subtitle">Things I made when I got bored</p>
            
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{{ projects|length }}</div>
                    <div class="stat-label">Projects</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{{ games }}</div>
                    <div class="stat-label">Games</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{{ tools }}</div>
                    <div class="stat-label">Tools</div>
                </div>
            </div>
        </header>
        
        {% if projects %}
        <div class="projects-grid">
            {% for project in projects %}
            <a href="/projects/{{ project.name }}" class="project-card">
                <span class="project-type type-{{ project.type }}">
                    {{ '🎮' if project.type == 'game' else '🛠️' }} {{ project.type }}
                </span>
                <h3 class="project-name">{{ project.name.replace('_', ' ').title() }}</h3>
                <p class="project-desc">{{ project.description }}</p>
                <p class="project-date">Created {{ project.created_at[:10] if project.created_at else 'recently' }}</p>
            </a>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <h2>Nothing here yet!</h2>
            <p>Zoe hasn't gotten bored enough to make anything... yet 😴</p>
            <p style="margin-top: 10px;">Leave her alone for 30 minutes and see what happens!</p>
        </div>
        {% endif %}
        
        <footer>
            <p>Autonomously created by Zoe when she got bored 🤖✨</p>
        </footer>
    </div>
</body>
</html>
"""

# ============================================================================
# Routes
# ============================================================================

@app.route("/")
def gallery():
    """Show gallery of all projects."""
    projects = get_all_projects()
    games = sum(1 for p in projects if p.get("type") == "game")
    tools = sum(1 for p in projects if p.get("type") == "tool")
    
    return render_template_string(
        GALLERY_TEMPLATE,
        projects=projects,
        games=games,
        tools=tools
    )

@app.route("/projects/<name>")
def project(name):
    """Serve a specific project's index.html."""
    project_dir = PROJECTS_DIR / name
    
    if not project_dir.exists() or not project_dir.is_dir():
        abort(404)
    
    index_file = project_dir / "index.html"
    if not index_file.exists():
        abort(404)
    
    return send_from_directory(project_dir, "index.html")

@app.route("/projects/<name>/<path:filename>")
def project_file(name, filename):
    """Serve additional project files (CSS, JS, images)."""
    project_dir = PROJECTS_DIR / name
    
    if not project_dir.exists():
        abort(404)
    
    return send_from_directory(project_dir, filename)

@app.route("/api/projects")
def api_projects():
    """API endpoint for project list."""
    projects = get_all_projects()
    return {"projects": projects}

# ============================================================================
# Helpers
# ============================================================================

def get_all_projects():
    """Get list of all created projects."""
    projects = []
    
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            metadata_file = project_dir / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        meta["name"] = project_dir.name
                        projects.append(meta)
                except:
                    # Project exists but no valid metadata
                    projects.append({
                        "name": project_dir.name,
                        "description": "A Zoe creation",
                        "type": "tool",
                        "created_at": None
                    })
    
    # Sort by creation date (newest first)
    projects.sort(key=lambda x: x.get("created_at", "") or "", reverse=True)
    return projects

# ============================================================================
# Run
# ============================================================================

def start_portal(background=True):
    """Start the portal server."""
    if background:
        import threading
        thread = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False), daemon=True)
        thread.start()
        print(f"🌐 Zoe Portal started at http://localhost:{PORT}")
        return thread
    else:
        print(f"🌐 Starting Zoe Portal at http://localhost:{PORT}")
        app.run(host="0.0.0.0", port=PORT, debug=True)

if __name__ == "__main__":
    start_portal(background=False)
