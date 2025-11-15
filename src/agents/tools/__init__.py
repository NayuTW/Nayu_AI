# Tools module
__all__ = []

# Smolagents-compatible tools
try:
    from .webbrowser_smol import WebBrowserSmolTool
    __all__.append("WebBrowserSmolTool")
except ImportError:
    pass

try:
    from .desktop_smol import DesktopSmolTool
    __all__.append("DesktopSmolTool")
except ImportError:
    pass

try:
    from .vision_smol import VisionSmolTool
    __all__.append("VisionSmolTool")
except ImportError:
    pass

try:
    from .memory_smol import MemorySmolTool
    __all__.append("MemorySmolTool")
except ImportError:
    pass

try:
    from .speech_smol import SpeechSmolTool
    __all__.append("SpeechSmolTool")
except ImportError:
    pass

try:
    from .discord_tool_smol import DiscordSmolTool
    __all__.append("DiscordSmolTool")
except ImportError:
    pass

try:
    from .discord_agent_tool import DiscordAgentTool
    __all__.append("DiscordAgentTool")
except ImportError:
    pass

# Legacy tools (for backward compatibility)
try:
    from .webbrowser import WebBrowserTool
    __all__.append("WebBrowserTool")
except ImportError:
    pass

try:
    from .desktop import DesktopTool
    __all__.append("DesktopTool")
except ImportError:
    pass

try:
    from .vision import VisionTool
    __all__.append("VisionTool")
except ImportError:
    pass

try:
    from .memory import MemoryTool
    __all__.append("MemoryTool")
except ImportError:
    pass

try:
    from .speech import SpeechTool
    __all__.append("SpeechTool")
except ImportError:
    pass
