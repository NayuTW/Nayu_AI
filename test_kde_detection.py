#!/usr/bin/env python3
"""
Test script to verify KDE Plasma detection in desktop tool.
This simulates the environment variables that would be present on Manjaro with KDE Plasma.
"""
import os
import sys


def test_kde_detection():
    """Test that KDE Plasma is correctly detected and described."""
    print("=" * 60)
    print("Testing KDE Plasma Detection")
    print("=" * 60)
    
    # Simulate KDE Plasma environment
    original_desktop = os.environ.get("XDG_CURRENT_DESKTOP", None)
    original_session = os.environ.get("XDG_SESSION_TYPE", None)
    
    try:
        # Set KDE Plasma environment variables
        os.environ["XDG_CURRENT_DESKTOP"] = "KDE"
        os.environ["XDG_SESSION_TYPE"] = "x11"
        
        print("\n1. Testing with KDE environment variables...")
        print(f"   XDG_CURRENT_DESKTOP: {os.environ['XDG_CURRENT_DESKTOP']}")
        print(f"   XDG_SESSION_TYPE: {os.environ['XDG_SESSION_TYPE']}")
        
        # Need to reload the module to pick up new environment variables
        import importlib
        import src.agents.tools.desktop_smol as desktop_module
        importlib.reload(desktop_module)
        
        from src.agents.tools.desktop_smol import get_os_info
        
        os_info = get_os_info()
        
        print(f"\n   OS Info:")
        print(f"     OS Type: {os_info['os']}")
        print(f"     Description: {os_info['description']}")
        print(f"     Desktop Environment: {os_info.get('desktop_environment', 'N/A')}")
        print(f"\n   Shortcuts Guide:")
        print(f"     {os_info['shortcuts_guide']}")
        
        # Verify KDE-specific information
        assert "KDE" in os_info['description'], "Description should contain 'KDE'"
        assert "kde" in os_info.get('desktop_environment', ''), "Desktop environment should be 'kde'"
        assert "Meta" in os_info['shortcuts_guide'] or "Super" in os_info['shortcuts_guide'], "Should mention Meta/Super key"
        assert "meta" in os_info['shortcuts_guide'].lower() or "super" in os_info['shortcuts_guide'].lower(), "Should recommend 'meta' or 'super' key"
        
        print("\n   ✓ KDE Plasma detection successful!")
        print("   ✓ Contains KDE-specific keyboard shortcuts")
        print("   ✓ Recommends using 'meta' or 'super' instead of 'win'")
        
        # Test the tool description
        print("\n2. Testing DesktopSmolTool description with KDE...")
        from src.agents.tools.desktop_smol import DesktopSmolTool
        
        desc = DesktopSmolTool.description
        print(f"\n   Full description:")
        print(f"   {desc}")
        
        assert "KDE" in desc, "Tool description should mention KDE"
        assert any(keyword in desc.lower() for keyword in ["meta", "super"]), "Description should mention Meta or Super key"
        
        print("\n   ✓ Tool description contains KDE-specific information")
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n   ✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n   ✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Restore original environment
        if original_desktop is not None:
            os.environ["XDG_CURRENT_DESKTOP"] = original_desktop
        elif "XDG_CURRENT_DESKTOP" in os.environ:
            del os.environ["XDG_CURRENT_DESKTOP"]
        
        if original_session is not None:
            os.environ["XDG_SESSION_TYPE"] = original_session
        elif "XDG_SESSION_TYPE" in os.environ:
            del os.environ["XDG_SESSION_TYPE"]


if __name__ == "__main__":
    sys.exit(test_kde_detection())
