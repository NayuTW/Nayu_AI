"""
DesktopTool converted to smolagents Tool class.
Controls keyboard, mouse, and takes screenshots.
"""
import time
import os
from typing import Dict, Any, Optional, List
from smolagents import Tool

try:
    import pyautogui
    import mss
    from PIL import Image
    DESKTOP_AVAILABLE = True
except ImportError:
    DESKTOP_AVAILABLE = False


class DesktopSmolTool(Tool):
    """
    Control keyboard and mouse, take screenshots.
    """
    name = "desktop"
    description = (
        "Control desktop via keyboard/mouse or take screenshots. "
        "Actions: 'screenshot' (returns the file path to the saved screenshot in .cache/), "
        "'click' (x, y coordinates), 'move' (x, y coordinates), "
        "'typewrite' (text string), 'hotkey' (keys list like ['ctrl', 'c'])"
    )
    inputs = {
        "action": {
            "type": "string",
            "description": "Action: screenshot, click, move, typewrite, or hotkey"
        },
        "x": {
            "type": "number",
            "description": "X coordinate for click/move actions",
            "nullable": True
        },
        "y": {
            "type": "number",
            "description": "Y coordinate for click/move actions",
            "nullable": True
        },
        "text": {
            "type": "string",
            "description": "Text to type for typewrite action",
            "nullable": True
        },
        "keys": {
            "type": "array",
            "description": "Keys for hotkey action (e.g., ['ctrl', 'c'])",
            "nullable": True
        }
    }
    output_type = "string"
    
    def __init__(self):
        super().__init__()
        if not DESKTOP_AVAILABLE:
            raise ImportError(
                "Desktop tools not available. Install with: pip install pyautogui mss Pillow"
            )
        pyautogui.FAILSAFE = True
        os.makedirs(".cache", exist_ok=True)
        self.last_screenshot_path = None
    
    def screenshot(self) -> str:
        """Take a screenshot and return the file path."""
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[1])
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            path = f".cache/screenshot_{int(time.time())}.png"
            img.save(path)
            self.last_screenshot_path = path
            return path
    
    def forward(
        self,
        action: str,
        x: Optional[float] = None,
        y: Optional[float] = None,
        text: Optional[str] = None,
        keys: Optional[List[str]] = None
    ) -> str:
        """Execute desktop action and return result description."""
        if action == "screenshot":
            path = self.screenshot()
            # Return just the path so it can be easily used by other tools like vision
            return path
        
        elif action == "move":
            if x is None or y is None:
                return "Error: x and y coordinates required for move action"
            pyautogui.moveTo(x, y, duration=0.2)
            return f"Moved mouse to ({x}, {y})"
        
        elif action == "click":
            if x is None or y is None:
                return "Error: x and y coordinates required for click action"
            pyautogui.click(x, y)
            return f"Clicked at ({x}, {y})"
        
        elif action == "typewrite":
            if not text:
                return "Error: text required for typewrite action"
            pyautogui.typewrite(text, interval=0.02)
            return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"
        
        elif action == "hotkey":
            if not keys:
                return "Error: keys list required for hotkey action"
            pyautogui.hotkey(*keys)
            return f"Pressed hotkey: {'+'.join(keys)}"
        
        else:
            return f"Error: Unknown action '{action}'. Valid actions: screenshot, move, click, typewrite, hotkey"
