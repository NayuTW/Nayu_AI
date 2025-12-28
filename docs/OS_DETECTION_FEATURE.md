# OS Detection Feature for Desktop Tool

## Problem
The agent was assuming Windows desktop environment and issuing Windows-specific hotkey commands (e.g., `win` key) regardless of the actual operating system. This caused issues on Linux systems like Manjaro with KDE Plasma, where different keyboard shortcuts and key names are used (e.g., `meta` or `super` instead of `win`).

## Solution
Added automatic OS and desktop environment detection to the desktop tool, with OS-specific keyboard shortcut guidance that is communicated to the agent through both the tool description and system prompt.

## Changes Made

### 1. Desktop Tool (`src/agents/tools/desktop_smol.py`)
- Added `get_os_info()` function that detects:
  - Operating system (Linux, Windows, macOS)
  - Desktop environment on Linux (KDE Plasma, GNOME, XFCE, etc.) via `XDG_CURRENT_DESKTOP`
  - Session type (X11, Wayland) via `XDG_SESSION_TYPE`
- Updated tool description to include OS-specific information
- Added OS-specific keyboard shortcut guidance:
  - **KDE Plasma**: Meta/Super key usage, KDE-specific shortcuts
  - **GNOME**: Super key usage, GNOME-specific shortcuts
  - **XFCE**: Alt-based shortcuts
  - **Generic Linux**: General Linux keyboard conventions
  - **Windows**: Win key shortcuts
  - **macOS**: Command key shortcuts

### 2. Main Agent (`src/agents/sub_agents/main_agent.py` and `src/agents/base_agent.py`)
- Added `os_context` field to store OS information
- Modified `_init_tools()` to capture OS context from desktop tool
- Updated prompt building to include OS context in system prompt
- Agent now receives clear information about the operating system and appropriate keyboard shortcuts

### 3. Tests
- `test_desktop_os_detection.py`: Tests basic OS detection functionality
- `test_kde_detection.py`: Simulates KDE Plasma environment and verifies correct detection

## How It Works

### OS Detection
```python
# Detects OS using platform.system()
os_type = platform.system()  # Returns: "Linux", "Windows", "Darwin" (macOS)

# On Linux, also detects desktop environment
desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "")  # e.g., "KDE", "GNOME"
session_type = os.environ.get("XDG_SESSION_TYPE", "")    # e.g., "x11", "wayland"
```

### Example Tool Description (KDE Plasma)
```
Control desktop via keyboard/mouse or take screenshots on Linux KDE (x11). 
Actions: 'screenshot' (saves to .cache/), 'click' (x, y coordinates), 
'move' (x, y coordinates), 'typewrite' (text string), 
'hotkey' (keys list like ['ctrl', 'c']). 
OS Info: KDE Plasma shortcuts: Meta/Super (Windows key) for app launcher, 
Meta+E for file manager, Meta+D for show desktop, Ctrl+Alt+T for terminal, 
Alt+Tab for window switching. Use 'meta' or 'super' key instead of 'win' key.
```

### System Prompt Addition
The OS context is also added to the system prompt:
```
SYSTEM INFO: Running on Linux KDE (x11). KDE Plasma shortcuts: Meta/Super (Windows key) 
for app launcher, Meta+E for file manager, Meta+D for show desktop, Ctrl+Alt+T for terminal, 
Alt+Tab for window switching. Use 'meta' or 'super' key instead of 'win' key.
```

## Benefits

1. **Prevents Cross-Platform Issues**: Agent no longer assumes Windows environment
2. **Accurate Key Names**: Uses correct key names for each platform (meta/super vs win)
3. **Desktop-Specific Guidance**: Provides shortcuts specific to KDE, GNOME, etc.
4. **Improved Reasoning**: Agent can reason about OS-appropriate actions
5. **Better User Experience**: Commands work correctly on user's actual environment

## Testing

Run the included tests to verify functionality:

```bash
# Test basic OS detection
python test_desktop_os_detection.py

# Test KDE Plasma detection
python test_kde_detection.py
```

## Supported Platforms

- **Linux**: Full support with desktop environment detection
  - KDE Plasma
  - GNOME
  - XFCE
  - Generic Linux (fallback)
- **Windows**: Full support with Windows-specific shortcuts
- **macOS**: Full support with macOS-specific shortcuts
- **Other**: Generic fallback guidance

## Future Enhancements

Potential improvements:
- Add more Linux desktop environments (Cinnamon, MATE, i3, etc.)
- Detect window manager in addition to desktop environment
- Support for custom keyboard shortcut schemes
- Localization for different keyboard layouts
