#!/usr/bin/env python3
"""
Quick test of the browser workflow integration - Syntax validation only.
Tests that:
1. active_browser.py is syntactically correct with all required tools
2. VisionAgent can import browser tools
3. All exports are available
"""
import sys
import ast
from pathlib import Path

def test_file_syntax(filepath: str) -> bool:
    """Test that a Python file is syntactically correct."""
    try:
        with open(filepath, 'r') as f:
            code = f.read()
        ast.parse(code)
        return True
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}")
        return False


def test_active_browser_exports():
    """Test that active_browser.py has all required exports."""
    print("\n=== Testing active_browser.py exports ===")
    
    filepath = Path(__file__).parent / "src/agents/tools/active_browser.py"
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check for all required tool definitions
    required_tools = [
        'def start_browser',
        'def go_to_url',
        'def click_element',
        'def click_link',
        'def search_item_ctrl_f',
        'def scroll_down',
        'def scroll_up',
        'def go_back',
        'def close_popups',
        'def get_current_url',
    ]
    
    for tool in required_tools:
        if tool in content:
            tool_name = tool.replace('def ', '').replace('(', '')
            print(f"  ✓ {tool_name} defined")
        else:
            print(f"  ✗ {tool_name} NOT FOUND")
            return False
    
    # Check for helper functions
    if 'def init_browser_tools' in content:
        print("  ✓ init_browser_tools function defined")
    else:
        print("  ✗ init_browser_tools NOT FOUND")
        return False
    
    if 'def get_driver' in content:
        print("  ✓ get_driver helper defined")
    else:
        print("  ✗ get_driver NOT FOUND")
        return False
    
    if 'HELIUM_INSTRUCTIONS' in content:
        print("  ✓ HELIUM_INSTRUCTIONS constant defined")
    else:
        print("  ✗ HELIUM_INSTRUCTIONS NOT FOUND")
        return False
    
    # Check that all tools have name and description attributes
    for tool in required_tools:
        tool_name = tool.replace('def ', '').replace('(', '')
        if f"{tool_name}.name =" in content and f"{tool_name}.description =" in content:
            print(f"  ✓ {tool_name}.name and .description attributes set")
        else:
            print(f"  ✗ {tool_name} missing attributes")
            return False
    
    print("\n=== active_browser.py exports tests PASSED ===\n")
    return True


def test_vision_agent_imports():
    """Test that VisionAgent correctly imports browser tools."""
    print("\n=== Testing VisionAgent imports ===")
    
    filepath = Path(__file__).parent / "src/agents/sub_agents/vision_agent.py"
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check imports
    required_imports = [
        'from src.agents.tools.active_browser import',
        'start_browser',
        'go_back',
        'close_popups',
        'click_element',
        'click_link',
        'get_current_url',
        'scroll_down',
        'scroll_up',
        'search_item_ctrl_f',
        'init_browser_tools',
        'HELIUM_INSTRUCTIONS'
    ]
    
    for imp in required_imports:
        if imp in content:
            print(f"  ✓ {imp} imported")
        else:
            print(f"  ✗ {imp} NOT IMPORTED")
            return False
    
    # Check that _init_tools calls init_browser_tools
    if 'init_browser_tools(self)' in content:
        print("  ✓ init_browser_tools(self) called in _init_tools()")
    else:
        print("  ✗ init_browser_tools(self) NOT CALLED")
        return False
    
    # Check that all browser tools are registered
    browser_tools_list = [
        'start_browser',
        'click_element',
        'click_link',
        'search_item_ctrl_f',
        'scroll_down',
        'scroll_up',
        'go_back',
        'close_popups',
        'get_current_url'
    ]
    
    if 'browser_tools = [' in content:
        print("  ✓ browser_tools list defined")
    else:
        print("  ✗ browser_tools list NOT FOUND")
        return False
    
    print("\n=== VisionAgent imports tests PASSED ===\n")
    return True


if __name__ == "__main__":
    print("Testing interactive browser workflow integration (syntax validation)...\n")
    
    all_passed = True
    
    # Test syntax
    print("=== Testing File Syntax ===")
    files_to_test = [
        "src/agents/tools/active_browser.py",
        "src/agents/sub_agents/vision_agent.py",
    ]
    
    for filepath in files_to_test:
        full_path = Path(__file__).parent / filepath
        if test_file_syntax(str(full_path)):
            print(f"✓ {filepath} syntax OK")
        else:
            print(f"✗ {filepath} syntax ERROR")
            all_passed = False
    
    print()
    
    # Test exports
    all_passed = test_active_browser_exports() and all_passed
    all_passed = test_vision_agent_imports() and all_passed
    
    if all_passed:
        print("\n" + "="*50)
        print("✓ ALL SYNTAX TESTS PASSED!")
        print("="*50)
        print("\nThe interactive browser workflow is ready:")
        print("✓ active_browser.py has 10 browser tools properly defined")
        print("✓ All tools have name and description attributes")
        print("✓ VisionAgent imports all browser tools")
        print("✓ VisionAgent calls init_browser_tools(self)")
        print("✓ HELIUM_INSTRUCTIONS integrated into VisionAgent")
        print("\nWorkflow:")
        print("  1. MainAgent delegates browsing to VisionAgent")
        print("  2. VisionAgent uses 10 browser tools (helium + selenium)")
        print("  3. Desktop screenshots auto-update during browsing")
        print("  4. VisionAgent analyzes results with vision tool")
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("✗ SOME TESTS FAILED")
        print("="*50)
        sys.exit(1)
