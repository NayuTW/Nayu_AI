# Example Agent Context with OS Detection

This document shows what the agent sees with the OS detection feature enabled.

## Example 1: Manjaro Linux with KDE Plasma

### Tool Description (visible to agent)
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
```
SYSTEM INFO: Running on Linux KDE (x11). KDE Plasma shortcuts: Meta/Super 
(Windows key) for app launcher, Meta+E for file manager, Meta+D for show 
desktop, Ctrl+Alt+T for terminal, Alt+Tab for window switching. Use 'meta' 
or 'super' key instead of 'win' key.
```

### Agent Behavior
✅ **Before**: Agent would try `['win', 'e']` for file manager (doesn't work on KDE)
✅ **After**: Agent uses `['meta', 'e']` or `['super', 'e']` (works correctly on KDE)

---

## Example 2: GNOME Desktop

### Tool Description
```
Control desktop via keyboard/mouse or take screenshots on Linux GNOME (wayland). 
Actions: 'screenshot' (saves to .cache/), 'click' (x, y coordinates), 
'move' (x, y coordinates), 'typewrite' (text string), 
'hotkey' (keys list like ['ctrl', 'c']). 
OS Info: GNOME shortcuts: Super (Windows key) for activities/launcher, 
Super+A for app grid, Alt+Tab for window switching, Ctrl+Alt+T for terminal. 
Use 'super' key instead of 'win' key.
```

### System Prompt Addition
```
SYSTEM INFO: Running on Linux GNOME (wayland). GNOME shortcuts: Super 
(Windows key) for activities/launcher, Super+A for app grid, Alt+Tab for 
window switching, Ctrl+Alt+T for terminal. Use 'super' key instead of 'win' key.
```

---

## Example 3: Windows

### Tool Description
```
Control desktop via keyboard/mouse or take screenshots on Windows. 
Actions: 'screenshot' (saves to .cache/), 'click' (x, y coordinates), 
'move' (x, y coordinates), 'typewrite' (text string), 
'hotkey' (keys list like ['ctrl', 'c']). 
OS Info: Windows shortcuts: Win key for Start menu, Win+E for Explorer, 
Win+D for show desktop, Alt+Tab for window switching, Ctrl+C/V for copy/paste.
```

### System Prompt Addition
```
SYSTEM INFO: Running on Windows. Windows shortcuts: Win key for Start menu, 
Win+E for Explorer, Win+D for show desktop, Alt+Tab for window switching, 
Ctrl+C/V for copy/paste.
```

### Agent Behavior
✅ Agent correctly uses `['win', 'e']` for Explorer on Windows

---

## Example 4: macOS

### Tool Description
```
Control desktop via keyboard/mouse or take screenshots on macOS. 
Actions: 'screenshot' (saves to .cache/), 'click' (x, y coordinates), 
'move' (x, y coordinates), 'typewrite' (text string), 
'hotkey' (keys list like ['ctrl', 'c']). 
OS Info: macOS shortcuts: Cmd+Space for Spotlight, Cmd+Tab for app switching, 
Cmd+C/V for copy/paste, Cmd+Q to quit. Use 'command' instead of 'ctrl' 
for most shortcuts.
```

### System Prompt Addition
```
SYSTEM INFO: Running on macOS. macOS shortcuts: Cmd+Space for Spotlight, 
Cmd+Tab for app switching, Cmd+C/V for copy/paste, Cmd+Q to quit. Use 
'command' instead of 'ctrl' for most shortcuts.
```

### Agent Behavior
✅ Agent correctly uses `['command', 'space']` for Spotlight instead of `['ctrl', 'space']`

---

## Key Improvements

1. **OS-Aware**: Agent knows which OS it's running on
2. **Desktop-Aware**: On Linux, knows about KDE, GNOME, XFCE, etc.
3. **Correct Key Names**: Uses `meta`/`super` on Linux, `win` on Windows, `command` on macOS
4. **Platform-Specific Shortcuts**: Knows KDE uses Meta+E while GNOME uses Super+A
5. **Prevents Errors**: Won't try Windows shortcuts on Linux or vice versa
