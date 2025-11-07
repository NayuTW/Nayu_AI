#!/usr/bin/env python3
"""
Test script to verify vision tool works with Ollama.
This test validates the vision tool can be instantiated and has correct parameters.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_vision_tool_import():
    """Test that VisionSmolTool can be imported."""
    print("=" * 60)
    print("Testing Vision Tool Ollama Migration")
    print("=" * 60)
    
    print("\n1. Testing VisionSmolTool import...")
    try:
        from agents.tools.vision_smol import VisionSmolTool
        print("   ✓ VisionSmolTool imported successfully")
        return True
    except ImportError as e:
        print(f"   ✗ Failed to import: {e}")
        return False


def test_vision_tool_instantiation():
    """Test that VisionSmolTool can be instantiated with new default."""
    print("\n2. Testing VisionSmolTool instantiation...")
    try:
        from agents.tools.vision_smol import VisionSmolTool
        
        # Test with default model (should be gemma3:4b-it-q4_K_M)
        tool = VisionSmolTool()
        
        if tool.model_id != "gemma3:4b-it-q4_K_M":
            print(f"   ✗ Default model is '{tool.model_id}', expected 'gemma3:4b-it-q4_K_M'")
            return False
        
        print(f"   ✓ VisionSmolTool created with default model: {tool.model_id}")
        print(f"   ✓ Ollama URL: {tool.ollama_url}")
        print(f"   ✓ Tool name: {tool.name}")
        
        return True
    except Exception as e:
        print(f"   ✗ Failed to instantiate: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vision_tool_custom_model():
    """Test that VisionSmolTool can be instantiated with custom model."""
    print("\n3. Testing VisionSmolTool with custom model...")
    try:
        from agents.tools.vision_smol import VisionSmolTool
        
        custom_model = "llava:7b"
        tool = VisionSmolTool(model_id=custom_model)
        
        if tool.model_id != custom_model:
            print(f"   ✗ Model is '{tool.model_id}', expected '{custom_model}'")
            return False
        
        print(f"   ✓ VisionSmolTool created with custom model: {tool.model_id}")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False


def test_vision_tool_no_transformers():
    """Test that VisionSmolTool doesn't import transformers."""
    print("\n4. Testing that transformers is not used...")
    try:
        from agents.tools.vision_smol import VisionSmolTool
        import sys
        
        # Check if transformers was imported
        if 'transformers' in sys.modules:
            print("   ✗ transformers module was imported (should not be used)")
            return False
        
        print("   ✓ transformers module not imported (correct)")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False


def test_vision_tool_has_encode_method():
    """Test that VisionSmolTool has the _encode_image method."""
    print("\n5. Testing _encode_image method exists...")
    try:
        from agents.tools.vision_smol import VisionSmolTool
        
        tool = VisionSmolTool()
        
        if not hasattr(tool, '_encode_image'):
            print("   ✗ _encode_image method not found")
            return False
        
        print("   ✓ _encode_image method exists")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False


def test_vision_tool_forward_signature():
    """Test that VisionSmolTool.forward has correct signature."""
    print("\n6. Testing forward method signature...")
    try:
        from agents.tools.vision_smol import VisionSmolTool
        import inspect
        
        tool = VisionSmolTool()
        sig = inspect.signature(tool.forward)
        params = list(sig.parameters.keys())
        
        if 'path' not in params or 'prompt' not in params:
            print(f"   ✗ Expected parameters 'path' and 'prompt', got: {params}")
            return False
        
        print(f"   ✓ forward method has correct parameters: {params}")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False


def main():
    """Run all tests."""
    tests = [
        test_vision_tool_import,
        test_vision_tool_instantiation,
        test_vision_tool_custom_model,
        test_vision_tool_no_transformers,
        test_vision_tool_has_encode_method,
        test_vision_tool_forward_signature,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n   ✗ Test {test.__name__} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    
    if passed < total:
        print("\n✗ Some tests failed")
        return 1
    else:
        print("\n✓ All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
