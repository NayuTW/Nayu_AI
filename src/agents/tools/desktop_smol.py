"""
DesktopTool converted to smolagents Tool class.
Controls keyboard, mouse, and takes screenshots.
"""
import time
import os
import platform
from typing import Dict, Any, Optional, List
from smolagents import Tool

try:
    import pyautogui
    import mss
    from PIL import Image
    DESKTOP_AVAILABLE = True
except ImportError:
    DESKTOP_AVAILABLE = False


def get_os_info() -> dict:
    """
    Get operating system information including platform and desktop environment.
    Returns a dictionary with OS details and common keyboard shortcuts.
    """
    os_type = platform.system()
    os_info = {
        "os": os_type,
        "description": "",
        "shortcuts_guide": ""
    }
    
    if os_type == "Linux":
        # Try to detect desktop environment
        desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        
        # Build description
        desc_parts = ["Linux"]
        if desktop_env:
            desc_parts.append(desktop_env.upper())
        if session_type:
            desc_parts.append(f"({session_type})")
        
        os_info["description"] = " ".join(desc_parts)
        os_info["desktop_environment"] = desktop_env
        
        # Provide Linux-specific keyboard shortcuts guidance
        if "kde" in desktop_env or "plasma" in desktop_env:
            os_info["shortcuts_guide"] = (
                "KDE Plasma shortcuts: Meta/Super (Windows key) for app launcher, "
                "Meta+E for file manager, Meta+D for show desktop, "
                "Ctrl+Alt+T for terminal, Alt+Tab for window switching. "
                "Use 'meta' or 'super' key instead of 'win' key."
            )
        elif "gnome" in desktop_env:
            os_info["shortcuts_guide"] = (
                "GNOME shortcuts: Super (Windows key) for activities/launcher, "
                "Super+A for app grid, Alt+Tab for window switching, "
                "Ctrl+Alt+T for terminal. Use 'super' key instead of 'win' key."
            )
        elif "xfce" in desktop_env:
            os_info["shortcuts_guide"] = (
                "XFCE shortcuts: Alt+F1 for app menu, Alt+F2 for run dialog, "
                "Alt+Tab for window switching, Ctrl+Alt+T for terminal."
            )
        else:
            os_info["shortcuts_guide"] = (
                "Linux shortcuts typically use Super/Meta (Windows key) or Alt modifiers. "
                "Common: Super for launcher, Alt+Tab for windows, Ctrl+Alt+T for terminal. "
                "Use 'super' or 'meta' key instead of 'win' key."
            )
    
    elif os_type == "Windows":
        os_info["description"] = "Windows"
        os_info["shortcuts_guide"] = (
            "Windows shortcuts: Win key for Start menu, Win+E for Explorer, "
            "Win+D for show desktop, Alt+Tab for window switching, "
            "Ctrl+C/V for copy/paste."
        )
    
    elif os_type == "Darwin":
        os_info["description"] = "macOS"
        os_info["shortcuts_guide"] = (
            "macOS shortcuts: Cmd+Space for Spotlight, Cmd+Tab for app switching, "
            "Cmd+C/V for copy/paste, Cmd+Q to quit. Use 'command' instead of 'ctrl' "
            "for most shortcuts."
        )
    
    else:
        os_info["description"] = os_type or "Unknown"
        os_info["shortcuts_guide"] = "OS-specific shortcuts may vary."
    
    return os_info


class DesktopSmolTool(Tool):
    """
    Control keyboard and mouse, take screenshots.
    """
    name = "desktop"
    
    # Generate OS-aware description
    _os_info = get_os_info()
    description = (
        f"Control desktop via keyboard/mouse or take screenshots on {_os_info.get('description', 'Unknown OS')}. "
        "Actions: 'screenshot' (saves to .cache/), 'click' (x, y coordinates), "
        "'move' (x, y coordinates), 'typewrite' (text string), "
        f"'hotkey' (keys list like ['ctrl', 'c']). "
        f"OS Info: {_os_info.get('shortcuts_guide', 'OS-specific shortcuts may vary.')}"
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
        self.os_info = get_os_info()
    
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
            return f"Screenshot saved to: {path}"
        
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
