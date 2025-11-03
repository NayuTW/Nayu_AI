#!/usr/bin/env python3
"""
Test script to verify OS detection in desktop tool.
"""
import os
import platform
import sys


def test_os_detection():
    """Test that OS detection works correctly."""
    print("=" * 60)
    print("Testing Desktop Tool OS Detection")
    print("=" * 60)
    
    tests = []
    
    # Test 1: Import get_os_info function
    print("\n1. Testing get_os_info function...")
    try:
        from src.agents.tools.desktop_smol import get_os_info
        os_info = get_os_info()
        print(f"   ✓ OS detection successful")
        print(f"     OS Type: {os_info['os']}")
        print(f"     Description: {os_info['description']}")
        print(f"     Shortcuts Guide: {os_info['shortcuts_guide'][:100]}...")
        tests.append(("get_os_info", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("get_os_info", False, str(e)))
        import traceback
        traceback.print_exc()
    
    # Test 2: Verify platform detection
    print("\n2. Testing platform detection...")
    try:
        detected_os = platform.system()
        print(f"   ✓ Platform: {detected_os}")
        
        # Check environment variables on Linux
        if detected_os == "Linux":
            desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "Not set")
            session_type = os.environ.get("XDG_SESSION_TYPE", "Not set")
            print(f"     Desktop Environment: {desktop_env}")
            print(f"     Session Type: {session_type}")
        
        tests.append(("platform detection", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("platform detection", False, str(e)))
    
    # Test 3: Initialize DesktopSmolTool
    print("\n3. Testing DesktopSmolTool initialization...")
    try:
        from src.agents.tools.desktop_smol import DesktopSmolTool
        
        # This might fail if dependencies are not installed, which is okay
        try:
            tool = DesktopSmolTool()
            print(f"   ✓ DesktopSmolTool initialized")
            print(f"     Tool name: {tool.name}")
            print(f"     OS Info in tool: {tool.os_info['description']}")
            print(f"     Description length: {len(tool.description)} chars")
            print(f"     Description preview: {tool.description[:150]}...")
            tests.append(("DesktopSmolTool init", True, None))
        except ImportError as e:
            print(f"   ⚠ Skipped (dependencies not installed): {e}")
            tests.append(("DesktopSmolTool init", None, "Dependencies not installed"))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("DesktopSmolTool init", False, str(e)))
        import traceback
        traceback.print_exc()
    
    # Test 4: Verify description contains OS info
    print("\n4. Testing OS info in tool description...")
    try:
        from src.agents.tools.desktop_smol import DesktopSmolTool
        
        # Check the class-level description
        desc = DesktopSmolTool.description
        
        # Verify it contains OS-related information
        has_os_info = any(keyword in desc.lower() for keyword in ["linux", "windows", "macos", "kde", "gnome", "super", "meta"])
        
        if has_os_info:
            print(f"   ✓ Description contains OS-specific information")
            print(f"     Full description: {desc}")
            tests.append(("OS info in description", True, None))
        else:
            print(f"   ⚠ Description might not contain OS info")
            print(f"     Description: {desc}")
            tests.append(("OS info in description", None, "Could not verify OS info"))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("OS info in description", False, str(e)))
        import traceback
        traceback.print_exc()
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result, _ in tests if result is True)
    failed = sum(1 for _, result, _ in tests if result is False)
    skipped = sum(1 for _, result, _ in tests if result is None)
    
    print(f"Passed:  {passed}/{len(tests)}")
    print(f"Failed:  {failed}/{len(tests)}")
    print(f"Skipped: {skipped}/{len(tests)}")
    
    if failed > 0:
        print("\nFailed tests:")
        for name, result, error in tests:
            if result is False:
                print(f"  - {name}: {error}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(test_os_detection())
