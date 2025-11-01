#!/usr/bin/env python3
"""
Test script to verify smolagents migration.
Run this after installing all dependencies from requirements.txt.
"""
import sys
import traceback


def test_imports():
    """Test that all smolagents components can be imported."""
    print("=" * 60)
    print("Testing Smolagents Migration Imports")
    print("=" * 60)
    
    tests = []
    
    # Test 1: smolagents core
    print("\n1. Testing smolagents core...")
    try:
        from smolagents import Tool, CodeAgent, LiteLLMModel
        print("   ✓ smolagents core imported successfully")
        tests.append(("smolagents core", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("smolagents core", False, str(e)))
    
    # Test 2: OllamaLiteLLMModel
    print("\n2. Testing OllamaLiteLLMModel...")
    try:
        import os
        from src.agents.llm.litellm_model import OllamaLiteLLMModel
        # Use environment variable or default for testing
        test_model = os.getenv("AGENT_MODEL", "llama3.1:8b-instruct-q4_K_M")
        model = OllamaLiteLLMModel(model_id=test_model, num_ctx=8192)
        print(f"   ✓ OllamaLiteLLMModel created: {model}")
        tests.append(("OllamaLiteLLMModel", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("OllamaLiteLLMModel", False, str(e)))
        traceback.print_exc()
    
    # Test 3: MemorySmolTool
    print("\n3. Testing MemorySmolTool...")
    try:
        from src.agents.tools.memory_smol import MemorySmolTool
        tool = MemorySmolTool()
        print(f"   ✓ MemorySmolTool created: {tool.name}")
        tests.append(("MemorySmolTool", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("MemorySmolTool", False, str(e)))
    
    # Test 4: DesktopSmolTool
    print("\n4. Testing DesktopSmolTool...")
    try:
        from src.agents.tools.desktop_smol import DesktopSmolTool
        tool = DesktopSmolTool()
        print(f"   ✓ DesktopSmolTool created: {tool.name}")
        tests.append(("DesktopSmolTool", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("DesktopSmolTool", False, str(e)))
    
    # Test 5: VisionSmolTool
    print("\n5. Testing VisionSmolTool...")
    try:
        from src.agents.tools.vision_smol import VisionSmolTool
        tool = VisionSmolTool()
        print(f"   ✓ VisionSmolTool created: {tool.name}")
        tests.append(("VisionSmolTool", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("VisionSmolTool", False, str(e)))
    
    # Test 6: SpeechSmolTool
    print("\n6. Testing SpeechSmolTool...")
    try:
        from src.agents.tools.speech_smol import SpeechSmolTool
        tool = SpeechSmolTool()
        print(f"   ✓ SpeechSmolTool created: {tool.name}")
        tests.append(("SpeechSmolTool", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("SpeechSmolTool", False, str(e)))
    
    # Test 7: WebBrowserSmolTool
    print("\n7. Testing WebBrowserSmolTool...")
    try:
        from src.agents.tools.webbrowser_smol import WebBrowserSmolTool
        tool = WebBrowserSmolTool()
        print(f"   ✓ WebBrowserSmolTool created: {tool.name}")
        tests.append(("WebBrowserSmolTool", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("WebBrowserSmolTool", False, str(e)))
    
    # Test 8: MainAgentSmol
    print("\n8. Testing MainAgentSmol...")
    try:
        from src.agents.main_agent import MainAgentSmol
        from src.agents.state import SharedState
        from src.agents.core.events import EventBus
        from src.agents.core.registry import ToolRegistry
        from src.agents.notify.notifier import Notifier
        from src.agents.core.store import SQLiteStore
        
        state = SharedState()
        store = SQLiteStore()
        bus = EventBus(store=store)
        registry = ToolRegistry(store=store)
        notifier = Notifier(speech_tool=None, voice_enabled=False, speak_on_error=False)
        
        agent = MainAgentSmol(
            state=state,
            bus=bus,
            registry=registry,
            notifier=notifier,
            store=store,
            session_id="test-session"
        )
        print(f"   ✓ MainAgentSmol created with {len(agent.tools)} tools")
        tests.append(("MainAgentSmol", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("MainAgentSmol", False, str(e)))
        traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(1 for _, success, _ in tests if success)
    total = len(tests)
    print(f"\nPassed: {passed}/{total}")
    
    if passed < total:
        print("\nFailed tests:")
        for name, success, error in tests:
            if not success:
                print(f"  - {name}: {error}")
        return 1
    else:
        print("\n✓ All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(test_imports())
