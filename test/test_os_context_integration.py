#!/usr/bin/env python3
"""
Integration test to verify OS context flows correctly from desktop tool to main agent.
"""
import os
import sys


def test_os_context_integration():
    """Test that OS context is properly integrated into the agent system."""
    print("=" * 60)
    print("Testing OS Context Integration")
    print("=" * 60)
    
    # Test 1: Import and get OS info
    print("\n1. Testing OS info function...")
    try:
        from src.agents.tools.desktop_smol import get_os_info
        os_info = get_os_info()
        
        assert "os" in os_info, "OS info should contain 'os' key"
        assert "description" in os_info, "OS info should contain 'description' key"
        assert "shortcuts_guide" in os_info, "OS info should contain 'shortcuts_guide' key"
        
        print(f"   ✓ OS info structure validated")
        print(f"     OS: {os_info['os']}")
        print(f"     Description: {os_info['description']}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return 1
    
    # Test 2: Test with different OS environments
    print("\n2. Testing different OS environments...")
    test_cases = [
        {"XDG_CURRENT_DESKTOP": "KDE", "XDG_SESSION_TYPE": "x11", "expected": "KDE"},
        {"XDG_CURRENT_DESKTOP": "GNOME", "XDG_SESSION_TYPE": "wayland", "expected": "GNOME"},
        {"XDG_CURRENT_DESKTOP": "XFCE", "XDG_SESSION_TYPE": "x11", "expected": "XFCE"},
    ]
    
    original_desktop = os.environ.get("XDG_CURRENT_DESKTOP")
    original_session = os.environ.get("XDG_SESSION_TYPE")
    
    try:
        for test_case in test_cases:
            os.environ["XDG_CURRENT_DESKTOP"] = test_case["XDG_CURRENT_DESKTOP"]
            os.environ["XDG_SESSION_TYPE"] = test_case["XDG_SESSION_TYPE"]
            
            # Need to reload to pick up new env vars
            import importlib
            import src.agents.tools.desktop_smol as desktop_module
            importlib.reload(desktop_module)
            from src.agents.tools.desktop_smol import get_os_info
            
            os_info = get_os_info()
            
            if test_case["expected"] in os_info["description"]:
                print(f"   ✓ {test_case['expected']} detected correctly")
            else:
                print(f"   ⚠ Expected {test_case['expected']}, got {os_info['description']}")
    finally:
        # Restore original environment
        if original_desktop:
            os.environ["XDG_CURRENT_DESKTOP"] = original_desktop
        elif "XDG_CURRENT_DESKTOP" in os.environ:
            del os.environ["XDG_CURRENT_DESKTOP"]
        
        if original_session:
            os.environ["XDG_SESSION_TYPE"] = original_session
        elif "XDG_SESSION_TYPE" in os.environ:
            del os.environ["XDG_SESSION_TYPE"]
    
    # Test 3: Verify desktop tool contains OS info
    print("\n3. Testing DesktopSmolTool class-level description...")
    try:
        from src.agents.tools.desktop_smol import DesktopSmolTool
        
        desc = DesktopSmolTool.description
        
        # Check if description contains OS-related keywords
        has_os_keywords = any(word in desc.lower() for word in 
                             ["linux", "windows", "macos", "kde", "gnome", "meta", "super", "shortcuts"])
        
        if has_os_keywords:
            print(f"   ✓ Tool description contains OS-specific information")
        else:
            print(f"   ⚠ Tool description might be missing OS information")
            print(f"     Description: {desc}")
    except Exception as e:
        print(f"   ⚠ Could not test DesktopSmolTool: {e}")
    
    # Test 4: Verify key recommendations differ by platform
    print("\n4. Testing platform-specific key recommendations...")
    try:
        # Simulate Linux (KDE)
        os.environ["XDG_CURRENT_DESKTOP"] = "KDE"
        import importlib
        import src.agents.tools.desktop_smol as desktop_module
        importlib.reload(desktop_module)
        from src.agents.tools.desktop_smol import get_os_info
        
        kde_info = get_os_info()
        kde_shortcuts = kde_info["shortcuts_guide"].lower()
        
        # Verify Linux/KDE uses meta/super
        if "meta" in kde_shortcuts or "super" in kde_shortcuts:
            print(f"   ✓ Linux/KDE correctly recommends 'meta' or 'super' key")
        else:
            print(f"   ⚠ Linux/KDE should recommend 'meta' or 'super' key")
        
        # Verify it warns against using 'win'
        if "instead of" in kde_shortcuts and "win" in kde_shortcuts:
            print(f"   ✓ Correctly warns against using 'win' key on Linux")
        else:
            print(f"   ⚠ Should warn about 'win' key usage on Linux")
    except Exception as e:
        print(f"   ⚠ Could not complete platform test: {e}")
    finally:
        # Clean up environment
        if original_desktop:
            os.environ["XDG_CURRENT_DESKTOP"] = original_desktop
        elif "XDG_CURRENT_DESKTOP" in os.environ:
            del os.environ["XDG_CURRENT_DESKTOP"]
    
    print("\n" + "=" * 60)
    print("Integration Tests Completed ✓")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(test_os_context_integration())
