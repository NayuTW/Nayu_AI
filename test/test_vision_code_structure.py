#!/usr/bin/env python3
"""
Test script to verify vision tool code structure without dependencies.
This test validates the code changes by analyzing the source file.
"""
import sys
import os
import re


def test_vision_tool_file_exists():
    """Test that vision_smol.py exists."""
    print("=" * 60)
    print("Testing Vision Tool Code Structure")
    print("=" * 60)
    
    print("\n1. Testing vision_smol.py exists...")
    vision_file = "src/agents/tools/vision_smol.py"
    if not os.path.exists(vision_file):
        print(f"   ✗ File not found: {vision_file}")
        return False
    print(f"   ✓ File exists: {vision_file}")
    return True


def test_default_model_is_gemma():
    """Test that default model is gemma3:4b-it-q4_K_M."""
    print("\n2. Testing default model is gemma3:4b-it-q4_K_M...")
    vision_file = "src/agents/tools/vision_smol.py"
    with open(vision_file, 'r') as f:
        content = f.read()
    
    # Check for default model in __init__ method
    if 'model_id: str = "gemma3:4b-it-q4_K_M"' not in content:
        print("   ✗ Default model not found or incorrect")
        return False
    
    print("   ✓ Default model is gemma3:4b-it-q4_K_M")
    return True


def test_no_transformers_imports():
    """Test that transformers imports are removed."""
    print("\n3. Testing transformers imports removed...")
    vision_file = "src/agents/tools/vision_smol.py"
    with open(vision_file, 'r') as f:
        content = f.read()
    
    # Check that transformers is not imported
    if 'from transformers import' in content or 'import transformers' in content:
        print("   ✗ transformers imports still present")
        return False
    
    # Check that torch is not imported
    if 'import torch' in content:
        print("   ✗ torch imports still present")
        return False
    
    print("   ✓ transformers and torch imports removed")
    return True


def test_aiohttp_import():
    """Test that aiohttp is imported."""
    print("\n4. Testing aiohttp import added...")
    vision_file = "src/agents/tools/vision_smol.py"
    with open(vision_file, 'r') as f:
        content = f.read()
    
    if 'import aiohttp' not in content:
        print("   ✗ aiohttp import not found")
        return False
    
    print("   ✓ aiohttp import present")
    return True


def test_base64_import():
    """Test that base64 is imported."""
    print("\n5. Testing base64 import added...")
    vision_file = "src/agents/tools/vision_smol.py"
    with open(vision_file, 'r') as f:
        content = f.read()
    
    if 'import base64' not in content:
        print("   ✗ base64 import not found")
        return False
    
    print("   ✓ base64 import present")
    return True


def test_ollama_url_parameter():
    """Test that ollama_url parameter exists in __init__."""
    print("\n6. Testing ollama_url and timeout parameters...")
    vision_file = "src/agents/tools/vision_smol.py"
    with open(vision_file, 'r') as f:
        content = f.read()
    
    if 'ollama_url: str = "http://localhost:11434"' not in content:
        print("   ✗ ollama_url parameter not found or incorrect")
        return False
    
    if 'timeout: int = 120' not in content:
        print("   ✗ timeout parameter not found or incorrect")
        return False
    
    if 'self.timeout' not in content:
        print("   ✗ self.timeout not stored")
        return False
    
    print("   ✓ ollama_url and timeout parameters present")
    return True


def test_encode_image_method():
    """Test that _encode_image method exists."""
    print("\n7. Testing _encode_image method...")
    vision_file = "src/agents/tools/vision_smol.py"
    with open(vision_file, 'r') as f:
        content = f.read()
    
    if 'def _encode_image(self, image_path: str) -> str:' not in content:
        print("   ✗ _encode_image method not found")
        return False
    
    if 'base64.b64encode' not in content:
        print("   ✗ base64 encoding not implemented")
        return False
    
    print("   ✓ _encode_image method present with base64 encoding")
    return True


def test_analyze_image_async_method():
    """Test that _analyze_image_async method exists."""
    print("\n8. Testing _analyze_image_async method...")
    vision_file = "src/agents/tools/vision_smol.py"
    with open(vision_file, 'r') as f:
        content = f.read()
    
    if 'async def _analyze_image_async' not in content:
        print("   ✗ _analyze_image_async method not found")
        return False
    
    print("   ✓ _analyze_image_async method present")
    return True


def test_ollama_api_endpoint():
    """Test that Ollama API endpoint is used."""
    print("\n9. Testing Ollama API endpoint...")
    vision_file = "src/agents/tools/vision_smol.py"
    with open(vision_file, 'r') as f:
        content = f.read()
    
    if '/api/generate' not in content:
        print("   ✗ Ollama /api/generate endpoint not found")
        return False
    
    print("   ✓ Ollama /api/generate endpoint present")
    return True


def test_documentation_updated():
    """Test that documentation files are updated."""
    print("\n10. Testing documentation updates...")
    
    success = True
    
    # Check README.md
    if os.path.exists("README.md"):
        with open("README.md", 'r') as f:
            readme = f.read()
        
        if "gemma3:4b-it-q4_K_M" in readme:
            print("   ✓ README.md updated with gemma3")
        else:
            print("   ✗ README.md not updated")
            success = False
    else:
        print("   ⚠ README.md not found")
    
    # Check copilot-instructions.md
    if os.path.exists(".github/copilot-instructions.md"):
        with open(".github/copilot-instructions.md", 'r') as f:
            copilot_md = f.read()
        
        if "gemma3:4b-it-q4_K_M" in copilot_md:
            print("   ✓ copilot-instructions.md updated with gemma3")
        else:
            print("   ✗ copilot-instructions.md not updated")
            success = False
    else:
        print("   ⚠ copilot-instructions.md not found")
    
    return success


def main():
    """Run all tests."""
    tests = [
        test_vision_tool_file_exists,
        test_default_model_is_gemma,
        test_no_transformers_imports,
        test_aiohttp_import,
        test_base64_import,
        test_ollama_url_parameter,
        test_encode_image_method,
        test_analyze_image_async_method,
        test_ollama_api_endpoint,
        test_documentation_updated,
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
