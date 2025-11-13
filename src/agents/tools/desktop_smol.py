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
    
    IMPORTANT: Desktop actions take time to complete. Always use proper delays:
    - After opening launcher: wait 0.5-1.0s before typing
    - After typing app name: wait 0.3-0.5s before pressing enter
    - After launching app: wait 2-3s for app to start
    - Use screenshot action to verify the current state before proceeding
    """
    name = "desktop"
    
    # Generate OS-aware description at class definition time.
    _os_info = get_os_info()
    description = (
        "Control desktop via keyboard/mouse or take screenshots. "
        "Actions: 'screenshot' (returns the file path to the saved screenshot in .cache/), "
        "'click' (x, y coordinates), 'move' (x, y coordinates), "
        "'type' (text string - for typing text only), "
        "'press' (key - for single keys like 'enter', 'tab', 'space'), "
        "'hotkey' (keys list like ['ctrl', 'c'] - for key combinations), "
        "'wait' (seconds - pause execution to let UI catch up). "
        "CRITICAL: Use 'press' for special keys (enter, tab, escape), NOT 'type'. "
        "CRITICAL: Always wait 0.5-1s after hotkeys before typing. "
        "CRITICAL: Always wait 0.3-0.5s after typing before pressing enter. "
        "CRITICAL: Take a screenshot to verify success before proceeding to next step."
    )
    inputs = {
        "action": {
            "type": "string",
            "description": "Action: screenshot, click, move, type, press, hotkey, or wait"
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
            "description": "Text to type (for 'type' action only - no special keys)",
            "nullable": True
        },
        "key": {
            "type": "string",
            "description": "Single key to press (for 'press' action: enter, tab, space, escape, etc.)",
            "nullable": True
        },
        "keys": {
            "type": "array",
            "description": "Keys for hotkey action (e.g., ['ctrl', 'c'])",
            "nullable": True
        },
        "seconds": {
            "type": "number",
            "description": "Seconds to wait (for 'wait' action, e.g., 0.5, 1.0, 2.0)",
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
        pyautogui.PAUSE = 0.1  # Small default pause between pyautogui actions
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
        key: Optional[str] = None,
        keys: Optional[List[str]] = None,
        seconds: Optional[float] = None
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
            time.sleep(0.1)  # Brief pause after click
            return f"Clicked at ({x}, {y})"
        
        elif action == "type":
            if not text:
                return "Error: text required for type action"
            # Use write() instead of typewrite() for better unicode support
            # But with a small interval to simulate human typing
            for char in text:
                pyautogui.write(char)
                time.sleep(0.02)  # 20ms between characters
            return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"
        
        elif action == "press":
            if not key:
                return "Error: key required for press action"
            # Normalize key names
            key_lower = key.lower()
            pyautogui.press(key_lower)
            time.sleep(0.1)  # Brief pause after key press
            return f"Pressed key: {key}"
        
        elif action == "hotkey":
            if not keys:
                return "Error: keys list required for hotkey action"
            pyautogui.hotkey(*keys)
            time.sleep(0.15)  # Slightly longer pause after hotkey combos
            return f"Pressed hotkey: {'+'.join(keys)}"
        
        elif action == "wait":
            if seconds is None:
                return "Error: seconds required for wait action"
            if seconds <= 0 or seconds > 10:
                return "Error: wait time must be between 0 and 10 seconds"
            time.sleep(seconds)
            return f"Waited {seconds} seconds"
        
        else:
            return (
                f"Error: Unknown action '{action}'. "
                "Valid actions: screenshot, move, click, type, press, hotkey, wait"
            )
