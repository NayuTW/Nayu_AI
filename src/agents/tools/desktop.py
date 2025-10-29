import time
from typing import Dict, Any
import pyautogui
import mss
from PIL import Image
import os

class DesktopTool:
    def __init__(self, state):
        self.state = state
        pyautogui.FAILSAFE = True
        os.makedirs(".cache", exist_ok=True)

    @staticmethod
    def spec():
        return {
            "name": "desktop",
            "description": "Control keyboard and mouse, take screenshots. Screenshot action saves to .cache/ and stores path in state.extra['last_screenshot_path'].",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["screenshot", "click", "move", "typewrite", "hotkey"], "description": "Action to perform"},
                    "x": {"type": "number", "description": "X coordinate for click/move actions"},
                    "y": {"type": "number", "description": "Y coordinate for click/move actions"},
                    "text": {"type": "string", "description": "Text to type for typewrite action"},
                    "keys": {"type": "array", "items": {"type": "string"}, "description": "Keys for hotkey action (e.g., ['ctrl', 'c'])"}
                },
                "required": ["action"]
            }
        }

    def screenshot(self):
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[1])
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            path = f".cache/screenshot_{int(time.time())}.png"
            img.save(path)
            return path

    async def run(self, action: str, x: float = 0, y: float = 0, text: str = "", keys=None) -> Dict[str, Any]:
        keys = keys or []
        summary = ""
        delta = {}
        if action == "screenshot":
            path = self.screenshot()
            summary = f"Screenshot saved: {path}"
            # Store the screenshot path in state for easy access by vision tool
            delta = {"last_observation": summary, "last_screenshot_path": path}
        elif action == "move":
            pyautogui.moveTo(x, y, duration=0.2)
            summary = f"Moved mouse to ({x},{y})"
            delta = {"last_observation": summary}
        elif action == "click":
            pyautogui.click(x, y)
            summary = f"Clicked at ({x},{y})"
            delta = {"last_observation": summary}
        elif action == "typewrite" and text:
            pyautogui.typewrite(text, interval=0.02)
            summary = f"Typed: {text[:50]}"
            delta = {"last_observation": summary}
        elif action == "hotkey" and keys:
            pyautogui.hotkey(*keys)
            summary = f"Pressed hotkey: {'+'.join(keys)}"
            delta = {"last_observation": summary}
        else:
            summary = "Invalid desktop action/args."
            delta = {"last_observation": summary}
        return {"summary": summary, "delta": delta}