"""
Tool Registry for Zoe ( Function Calling)
"""
import json
from typing import List, Dict, Any, Callable
from tool_maps import (
    search_web, read_url, read_file, list_dir, 
    create_folder, write_file, delete_folder, delete_file,
    deploy_site,
    open_url, open_app, take_screenshot
)
from ai_coder import ask_coder
import layer_b_tools
import layer_a_tools
import layer_c_tools

# Tool Implementations Map
TOOL_FUNCTIONS: Dict[str, Callable] = {
    "search_web": search_web,
    "read_url": read_url,
    "read_file": read_file,
    "list_dir": list_dir,
    "create_folder": create_folder,
    "write_file": write_file,
    "delete_folder": delete_folder,
    "delete_file": delete_file,
    "ask_coder": ask_coder,
    "deploy_site": deploy_site,
    "open_url": open_url,
    "open_app": open_app,
    "take_screenshot": take_screenshot,
    # Layer B Tools
    "manage_process": layer_b_tools.manage_process,
    "list_processes": layer_b_tools.list_processes,
    "scan_folder": layer_b_tools.scan_folder,
    "propose_organize": layer_b_tools.propose_organize,
    "apply_file_ops": layer_b_tools.apply_file_ops,
    # Layer A Tools (Browser)
    "launch_browser": layer_a_tools.launch_browser,
    "browser_navigate": layer_a_tools.browser_navigate,
    "browser_click": layer_a_tools.browser_click,
    "browser_type": layer_a_tools.browser_type,
    "browser_snapshot": layer_a_tools.browser_snapshot,
    # Layer C Tools (Vision Desktop)
    "capture_screen": layer_c_tools.capture_screen,
    "mouse_click": layer_c_tools.mouse_click,
    "keyboard_type": layer_c_tools.keyboard_type,
    "keyboard_hotkey": layer_c_tools.keyboard_hotkey,
    "get_screen_info": layer_c_tools.get_screen_info,
}

#  Tool Schemas
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the internet for current information, news, or facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g. 'latest AI news', 'weather in SF')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Read the content of a specific webpage URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to read."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_game_server",
            "description": "Start, stop, or check status of game servers (Minecraft, Valheim, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "status", "list"],
                        "description": "The action to perform."
                    },
                    "server_name": {
                        "type": "string",
                        "description": "The name of the server (e.g. 'valheim', 'minecraft'). Optional for 'list'."
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "paper_trade",
            "description": "Place a paper trade on Polymarket prediction markets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market_query": {
                        "type": "string",
                        "description": "Search term or ID for the market (e.g. 'Bitcoin 100k')."
                    },
                    "side": {
                        "type": "string",
                        "enum": ["yes", "no"],
                        "description": "Position to take."
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount of fake USD to trade (default 100)."
                    }
                },
                "required": ["market_query", "side"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a local file. Use this to analyze code, logs, or documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the directory."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder. Use location='playground' for Zoe's creative projects, or 'desktop' for user Desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_name": {
                        "type": "string",
                        "description": "The name of the folder to create (e.g. 'my-website')."
                    },
                    "location": {
                        "type": "string",
                        "description": "Target location alias ('desktop', 'playground') OR absolute path (e.g. 'C:/Users/josha/foo').",
                        "default": "playground"
                    }
                },
                "required": ["folder_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with content. Use for creating HTML, CSS, JS, text files, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to create (e.g. 'index.html', 'style.css')."
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file."
                    },
                    "location": {
                        "type": "string",
                        "description": "Target location alias ('desktop', 'playground') OR absolute path.",
                        "default": "playground"
                    }
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_folder",
            "description": "Delete a folder (and its contents if not empty).",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_name": {
                        "type": "string",
                        "description": "Name of the folder to delete."
                    },
                    "location": {
                        "type": "string",
                        "description": "Location alias ('desktop', 'playground') OR absolute path.",
                        "default": "desktop"
                    }
                },
                "required": ["folder_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to delete."
                    },
                    "location": {
                        "type": "string",
                        "description": "Location alias ('desktop', 'playground') OR absolute path.",
                        "default": "playground"
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_coder",
            "description": "Ask an advanced AI coding assistant for help with complex coding tasks. Use this for generating code, debugging, or architectural advice. Falls back through Claude → Gemini.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The coding task or question (e.g., 'Create an HTML page with animated buttons')."
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional context about existing code or project requirements."
                    }
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deploy_site",
            "description": "Deploy a project folder from your playground to Netlify. Returns the public URL. Only deploy when you're satisfied with the project!",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_name": {
                        "type": "string",
                        "description": "Name of the folder in your playground to deploy (must contain index.html)."
                    },
                    "site_name": {
                        "type": "string",
                        "description": "Optional custom site name/slug for the URL (e.g., 'zoe-cool-project')."
                    }
                },
                "required": ["folder_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a specific URL in the user's default web browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Address to open (e.g. https://google.com)."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Launch a desktop application (Spotify, Notepad, Calculator, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the app to launch."
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Capture the current screen content so Zoe can see what the user sees.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_process",
            "description": "Start, stop, or check a desktop application process (Layer B automation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "check"],
                        "description": "Action to perform."
                    },
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application (e.g. 'notepad', 'spotify', 'chrome')."
                    }
                },
                "required": ["action", "app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "List currently running processes on the desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_name": {
                        "type": "string",
                        "description": "Optional filter string to find specific apps."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scan_folder",
            "description": "Analyze a folder's contents to see file types, sizes, and age.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the folder."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_organize",
            "description": "Generate a plan to organize a messy folder (Inbox Zero). Returns a JSON plan for user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the folder to organize."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_file_ops",
            "description": "Execute a file organization plan. ONLY call this after the user has explicitly approved the plan from 'propose_organize'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_json_str": {
                        "type": "string",
                        "description": "The JSON plan string returned by propose_organize."
                    }
                },
                "required": ["plan_json_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "launch_browser",
            "description": "Launch a new browser session (Layer A). Use headless=False to let the user watch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Optional starting URL."
                    },
                    "headless": {
                        "type": "boolean",
                        "description": "Run in background? Default False (visible).",
                        "default": False
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Navigate the active browser to a specific URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The target URL."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element in the browser. Use 'browser_snapshot' first to find the right selector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector or text description of the element to click."
                    }
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": "Type text into an input field in the browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector of the input field."
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type."
                    }
                },
                "required": ["selector", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_snapshot",
            "description": "Get a semantic snapshot of the current page structure to decide the next action. Also saves a screenshot for user.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_screen",
            "description": "Layer C: Capture a screenshot of the desktop to pinpoint UI elements.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_click",
            "description": "Layer C: Click specific screen coordinates. DANGEROUS: Verify coordinates with 'get_screen_info' or 'capture_screen' first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"},
                    "button": {"type": "string", "enum": ["left", "right"], "default": "left"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "keyboard_type",
            "description": "Layer C: Type text using the keyboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "keyboard_hotkey",
            "description": "Layer C: Press a key combination (e.g. 'ctrl,c', 'alt,tab').",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "string", "description": "Comma-separated keys (e.g. 'ctrl,v')"}
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_screen_info",
            "description": "Layer C: Get screen resolution and mouse position.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

async def execute_tool_calls(tool_calls: List[Dict[str, Any]], bot=None) -> List[Dict[str, Any]]:
    """
    Execute a list of tool calls from  and return results.
    """
    import inspect
    
    results = []
    
    for tool in tool_calls:
        fn_name = tool["function"]["name"]
        args = tool["function"]["arguments"]
        
        print(f"🛠️ Executing Tool: {fn_name} with args: {args}")
        
        if fn_name not in TOOL_FUNCTIONS:
            results.append({
                "role": "tool",
                "content": f"Error: Tool '{fn_name}' not found.",
            })
            continue
            
        function_to_call = TOOL_FUNCTIONS[fn_name]
        
        try:
            # Check if function is async
            if inspect.iscoroutinefunction(function_to_call):
                # Check if it needs 'bot' (hacky dependency injection)
                # Currently none of our tool_maps functions need 'bot', 
                # but manage_game_server might in future.
                # For now, simple await.
                result = await function_to_call(**args)
            else:
                result = function_to_call(**args)
                
            results.append({
                "role": "tool",
                "content": str(result),
            })
            print(f"   ✅ Result: {str(result)[:50]}...")
            
        except Exception as e:
            error_msg = f"Error executing {fn_name}: {str(e)}"
            print(f"   ❌ {error_msg}")
            results.append({
                "role": "tool",
                "content": error_msg,
            })
            
    return results
