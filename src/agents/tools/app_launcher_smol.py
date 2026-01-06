"""
High-level application launcher tool.
Wraps desktop tool with proper delays and verification.
"""
import os
import subprocess
import sys
import time
import shutil
from typing import Optional
from smolagents import Tool


class AppLauncherSmolTool(Tool):
    """
    Launch applications with proper timing.
    Handles the complexity of opening app launchers and starting programs.
    """
    name = "launch_app"
    description = (
        "Launch a desktop application by name. "
        "Example usage: launch_app(app_name='chromium') - just provide the app name. "
        "Returns: success status. Use vision_agent to verify the application opened."
    )
    inputs = {
        "app_name": {
            "type": "string",
            "description": "Name of the application to launch (e.g., 'chromium', 'firefox', 'terminal')"
        }
    }
    output_type = "string"
    
    def __init__(self, desktop_tool):
        super().__init__()
        self.desktop = desktop_tool

    def _find_terminal(self) -> Optional[tuple[str, Optional[str]]]:
        """
        Find an available terminal emulator and the argument it uses for working-directory (if any).
        Returns tuple (executable, workdir_flag) or None if none found.
        workdir_flag is e.g. '--working-directory' or '-d' or '--workdir' or None if unsupported.
        """
        candidates = [
            ("gnome-terminal", "--working-directory"),
            ("alacritty", "--working-directory"),
            ("xfce4-terminal", "--working-directory"),
            ("konsole", "--workdir"),
            ("terminator", "--working-directory"),
            ("tilix", "--working-directory"),
            ("mate-terminal", "--working-directory"),
            ("lxterminal", "--working-directory"),
            ("urxvt", None),
            ("xterm", None),
            ("kitty", "--directory"),
            ("rxvt-unicode", None),
        ]
        for exe, flag in candidates:
            if shutil.which(exe):
                return exe, flag
        # fallback to x-terminal-emulator (Debian alternatives)
        if shutil.which("x-terminal-emulator"):
            return "x-terminal-emulator", None
        return None

    def _launch_terminal_linux(self, workspace_path: str) -> subprocess.Popen:
        found = self._find_terminal()
        if not found:
            raise FileNotFoundError("No known terminal emulator found on PATH.")
        exe, workdir_flag = found
        if workdir_flag:
            # Use flag style that supports setting working directory
            cmd = [exe, workdir_flag, workspace_path]
        else:
            target_display = ":0.0"
            env = os.environ.copy()
            env["DISPLAY"] = target_display
            # Terminals without a direct workdir flag: ask them to run a shell that cds then execs
            # Use bash -lc 'cd <workspace> && exec bash' as the command passed to -e
            if exe in ("xterm", "urxvt", "rxvt-unicode"):
                cmd = [exe, "-e", f"bash -lc 'cd \"{workspace_path}\" && exec bash'"]
            else:
                # Generic fallback
                cmd = [exe]
        return subprocess.Popen(cmd, env=os.environ.copy())

    def forward(self, app_name: str) -> str:
        """Launch an application with proper timing and arguments tailored per app."""
        workspace_path = os.path.abspath(".workspace")
        os.makedirs(workspace_path, exist_ok=True)
        target_display = ":0.0"
        env = os.environ.copy()
        env["DISPLAY"] = target_display

        try:
            app_lower = app_name.lower().strip()

            # Terminal handling
            if app_lower in ("terminal", "term", "terminal-app", "shell"):
                if sys.platform == "win32":
                    # Prefer Windows Terminal (wt) if available
                    if shutil.which("wt"):
                        cmd = ["wt", "-d", workspace_path]
                        subprocess.Popen(cmd, env=env)
                    else:
                        # Fallback to cmd.exe
                        # Use start via shell to open a new window
                        subprocess.Popen(f'start cmd /K "cd /d {workspace_path}"', shell=True, env=env)
                elif sys.platform == "darwin":
                    # Use AppleScript to open Terminal.app with a working directory
                    osa_cmd = [
                        "osascript",
                        "-e",
                        f'tell application "Terminal" to do script "cd {workspace_path} && exec $SHELL"',
                        "-e",
                        "tell application \"Terminal\" to activate"
                    ]
                    subprocess.Popen(osa_cmd, env=env)
                else:
                    # Linux variants
                    proc = self._launch_terminal_linux(workspace_path)
                    # proc already started
            else:
                # Generic GUI apps or commands: try to execute the binary directly.
                exe = shutil.which(app_name)
                if not exe:
                    # allow user to pass full path or arguments: try splitting on spaces to attempt execution
                    parts = app_name.split()
                    if shutil.which(parts[0]):
                        exe = parts[0]
                        cmd = parts
                    else:
                        return f"Executable '{app_name}' not found on PATH."
                if exe:
                    # For graphical apps like chromium, run them normally.
                    # Do not change cwd for GUI apps unless they are terminals.
                    # If the user passed extra args (e.g., 'code --new-window'), preserve them.
                    if app_name != exe:
                        # user provided args
                        cmd = app_name.split()
                    else:
                        cmd = [exe]
                    subprocess.Popen(cmd, env=env)

            # small delay to allow window to appear
            time.sleep(0.5)

            return (
                f"Launched {app_name} successfully. "
                f"You can use vision_agent to verify the application opened correctly."
            )
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return f"Error launching {app_name}: {str(e)}\n{error_details}"
