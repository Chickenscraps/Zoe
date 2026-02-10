"""
Vibe Engine
Generates aesthetic systems for creative projects.
Produces VIBE.md, palette.css, and palette.json.
"""
import os
import json
import logging
import asyncio
from typing import Dict, Any
from pathlib import Path
from model_router import router

logger = logging.getLogger(__name__)

class VibeEngine:
    async def generate_vibe_pack(self, project_path: Path, goal: str, constraints: str = "") -> bool:
        """
        Generate a Vibe Pack for the project.
        """
        logger.info(f"🎨 Generating Vibe Pack for {project_path.name}...")
        
        system_prompt = """You are Zoe's Vibe Engine.
Your goal: specific, high-quality design systems.
Input: Project Goal + Constraints.
Output: JSON object with:
- vibe_keywords: list[str]
- color_palette: list[dict] {name, hex, usage} (5-7 colors)
- typography: {heading, body, code} (suggested Google Fonts)
- ui_rules: list[str] (border-radius, spacing, effects)
- motion_rules: list[str] (easings, durations)
- css_variables: dict[str, str] (mapped to palette/rules)
- audio_motifs: list[str] (sound descriptions)
"""
        
        user_prompt = f"Goal: {goal}\nConstraints: {constraints}\n\nGenerate the design system."
        
        messages = [
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            # 1. Generate JSON Data
            # We ask for JSON specifically
            response = await router.chat(messages, system=system_prompt + "\nRETURN ONLY JSON.")
            
            # Clean response
            json_str = response.replace("```json", "").replace("```", "").strip()
            vibe_data = json.loads(json_str)
            
            # 2. Write Artifacts
            artifacts_dir = project_path / "ARTIFACTS"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            
            # palette.json
            with open(artifacts_dir / "palette.json", "w", encoding="utf-8") as f:
                json.dump(vibe_data, f, indent=2)
                
            # palette.css
            css_content = ":root {\n"
            for key, val in vibe_data.get("css_variables", {}).items():
                css_content += f"  {key}: {val};\n"
            css_content += "}\n"
            
            with open(artifacts_dir / "palette.css", "w", encoding="utf-8") as f:
                f.write(css_content)
                
            # VIBE.md
            vibe_md = f"""# Vibe: {goal}

## Keywords
{", ".join(vibe_data.get("vibe_keywords", []))}

## Palette
| Name | Hex | Usage |
|------|-----|-------|
"""
            for color in vibe_data.get("color_palette", []):
                vibe_md += f"| {color['name']} | `{color['hex']}` | {color['usage']} |\n"
                
            vibe_md += f"""
## Typography
- **Headings**: {vibe_data.get('typography', {}).get('heading')}
- **Body**: {vibe_data.get('typography', {}).get('body')}
- **Code**: {vibe_data.get('typography', {}).get('code')}

## UI Rules
"""
            for rule in vibe_data.get("ui_rules", []):
                vibe_md += f"- {rule}\n"
                
            vibe_md += "\n## Motion\n"
            for rule in vibe_data.get("motion_rules", []):
                vibe_md += f"- {rule}\n"
                
            with open(artifacts_dir / "VIBE.md", "w", encoding="utf-8") as f:
                f.write(vibe_md)
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate vibe pack: {e}")
            return False

# Export singleton
vibe_engine = VibeEngine()
