"""
High-level application launcher tool.
Wraps desktop tool with proper delays and verification.
"""
import time
from typing import Optional
from smolagents import Tool


class AppLauncherSmolTool(Tool):
    """
    Launch applications with proper timing and verification.
    Handles the complexity of opening app launchers and starting programs.
    """
    name = "launch_app"
    description = (
        "Launch a desktop application by name. "
        "This tool handles all the timing and UI interactions automatically. "
        "Usage: launch_app(app_name='chromium') - just provide the app name. "
        "Returns: success status and screenshot path for verification."
    )
    inputs = {
        "app_name": {
            "type": "string",
            "description": "Name of the application to launch (e.g., 'chromium', 'firefox', 'terminal')"
        }
    }
    output_type = "string"
    
    def __init__(self, desktop_tool, vision_tool=None):
        super().__init__()
        self.desktop = desktop_tool
        self.vision = vision_tool
    
    def forward(self, app_name: str) -> str:
        """Launch an application with proper timing."""
        try:
            # Step 1: Open launcher
            self.desktop.forward(action="hotkey", keys=["super"])
            time.sleep(0.8)
            
            # Step 2: Type app name
            self.desktop.forward(action="type", text=app_name.lower())
            time.sleep(0.4)
            
            # Step 3: Press enter
            self.desktop.forward(action="press", key="enter")
            time.sleep(3.0)  # Wait for app to launch
            
            # Step 4: Take screenshot for verification
            screenshot_path = self.desktop.forward(action="screenshot")
            
            return (
                f"Launched {app_name}. "
                f"Screenshot saved to: {screenshot_path}. "
                f"Use vision tool to verify the application opened successfully."
            )
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return f"Error launching {app_name}: {str(e)}\n{error_details}"
