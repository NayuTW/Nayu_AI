"""
DesktopTool converted to smolagents Tool class.
Controls keyboard, mouse, and takes screenshots.
"""
import time
import os
import platform
import json
import threading
from typing import Any, Optional
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

    CURRENT_PATH = ".cache/desktop_current.png"
    CURRENT_META_PATH = ".cache/desktop_current.json"
    
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
            "description": "Action: screenshot, current_screenshot, start_auto_capture, stop_auto_capture, click, move, type, press, hotkey, or wait"
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

        self._auto_capture_thread: Optional[threading.Thread] = None
        self._auto_capture_stop_event = threading.Event()
        self._auto_capture_interval = 1.0
        self._auto_capture_lock = threading.Lock()

    def _atomic_write_bytes(self, final_path: str, data: bytes) -> None:
        """Write bytes to a temp file then atomically replace the target."""
        tmp_path = f"{final_path}.tmp.{os.getpid()}.{int(time.time() * 1000)}"
        with open(tmp_path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)

    def _atomic_write_json(self, final_path: str, obj: dict) -> None:
        """Write JSON to a temp file then atomically replace the target."""
        tmp_path = f"{final_path}.tmp.{os.getpid()}.{int(time.time() * 1000)}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)

    def update_current_screenshot(self) -> str:
        """Capture and atomically update the stable current screenshot + metadata."""
        with self._auto_capture_lock:
            with mss.mss() as sct:
                shot = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", shot.size, shot.rgb)

            # Save to bytes first, then atomically replace.
            from io import BytesIO

            buf = BytesIO()
            img.save(buf, format="PNG")
            self._atomic_write_bytes(self.CURRENT_PATH, buf.getvalue())

            meta = {
                "timestamp": int(time.time()),
                "path": self.CURRENT_PATH,
                "width": img.size[0],
                "height": img.size[1],
            }
            self._atomic_write_json(self.CURRENT_META_PATH, meta)

            self.last_screenshot_path = self.CURRENT_PATH
            return self.CURRENT_PATH

    def get_current_path(self) -> str:
        """Ensure the stable current screenshot exists and return its path."""
        if not os.path.exists(self.CURRENT_PATH):
            return self.update_current_screenshot()
        return self.CURRENT_PATH

    def _auto_capture_loop(self) -> None:
        while not self._auto_capture_stop_event.is_set():
            try:
                self.update_current_screenshot()
            except Exception:
                # Best-effort loop: keep running even if one capture fails.
                pass
            self._auto_capture_stop_event.wait(self._auto_capture_interval)

    def start_auto_capture(self, interval: float = 1.0) -> str:
        """Start background loop that updates the stable current screenshot periodically."""
        if interval <= 0:
            return "Error: interval must be > 0"
        self._auto_capture_interval = float(interval)

        if self._auto_capture_thread and self._auto_capture_thread.is_alive():
            return f"Auto capture already running (interval={self._auto_capture_interval}s)"

        self._auto_capture_stop_event.clear()
        self._auto_capture_thread = threading.Thread(
            target=self._auto_capture_loop,
            name="desktop_auto_capture",
            daemon=True,
        )
        self._auto_capture_thread.start()
        return f"Started auto capture (interval={self._auto_capture_interval}s)"

    def stop_auto_capture(self) -> str:
        """Stop background auto capture."""
        if not self._auto_capture_thread or not self._auto_capture_thread.is_alive():
            return "Auto capture not running"

        self._auto_capture_stop_event.set()
        self._auto_capture_thread.join(timeout=2.0)
        return "Stopped auto capture"
    
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
        keys: Optional[list[str]] = None,
        seconds: Optional[float] = None
    ) -> str:
        """Execute desktop action and return result description."""
        if action == "screenshot":
            path = self.screenshot()
            # Return just the path so it can be easily used by other tools like vision
            return path

        elif action == "current_screenshot":
            return self.update_current_screenshot()

        elif action == "start_auto_capture":
            interval = 1.0 if seconds is None else float(seconds)
            return self.start_auto_capture(interval=interval)

        elif action == "stop_auto_capture":
            return self.stop_auto_capture()
        
        elif action == "move":
            if x is None or y is None:
                return "Error: x and y coordinates required for move action"
            pyautogui.moveTo(x, y, duration=0.2)
            # Keep stable screenshot fresh after state changes (optional but useful).
            self.update_current_screenshot()
            return f"Moved mouse to ({x}, {y})"
        
        elif action == "click":
            if x is None or y is None:
                return "Error: x and y coordinates required for click action"
            pyautogui.click(x, y)
            time.sleep(0.1)  # Brief pause after click
            self.update_current_screenshot()
            return f"Clicked at ({x}, {y})"
        
        elif action == "type":
            if not text:
                return "Error: text required for type action"
            # Use write() instead of typewrite() for better unicode support
            # But with a small interval to simulate human typing
            for char in text:
                pyautogui.write(char)
                time.sleep(0.02)  # 20ms between characters
            self.update_current_screenshot()
            return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"
        
        elif action == "press":
            if not key:
                return "Error: key required for press action"
            # Normalize key names
            key_lower = key.lower()
            pyautogui.press(key_lower)
            time.sleep(0.1)  # Brief pause after key press
            self.update_current_screenshot()
            return f"Pressed key: {key}"
        
        elif action == "hotkey":
            if not keys:
                return "Error: keys list required for hotkey action"
            pyautogui.hotkey(*keys)
            time.sleep(0.15)  # Slightly longer pause after hotkey combos
            self.update_current_screenshot()
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
                "Valid actions: screenshot, current_screenshot, start_auto_capture, stop_auto_capture, move, click, type, press, hotkey, wait"
            )
