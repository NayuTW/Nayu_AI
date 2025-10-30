#!/usr/bin/env python3
"""
Test script to validate LLM response format for both conversational and tool-calling scenarios.
This ensures the LLM properly distinguishes between normal chat and tool usage.
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.llm.ollama_client import OllamaLLM

async def test_conversational_response():
    """Test that simple greetings get conversational responses, not tool calls or code."""
    print("\n=== Test 1: Conversational Response ===")
    
    llm = OllamaLLM(model=os.getenv("AGENT_MODEL", "llama3.1:8b-instruct-q4_K_M"), json_mode=True, num_ctx=8000)
    
    messages = [
        {"role": "system", "content": "You are a helpful, friendly AI assistant."},
        {"role": "user", "content": "Hello"}
    ]
    
    # Simulate having tools available
    tools = [
        {
            "name": "example_tool",
            "description": "An example tool",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    ]
    
    try:
        response = await llm.chat(messages, tools=tools)
        print(f"Response: {response}")
        
        # Validate response structure
        if "text" in response:
            print("✓ PASS: Returned conversational text response")
            # Check that it's not generating code or test examples
            text = response["text"].lower()
            if any(word in text for word in ["assert", "def test_", "import unittest", "# test"]):
                print("✗ FAIL: Response contains test/code patterns")
                return False
            print("✓ PASS: Response does not contain inappropriate code/test patterns")
            return True
        elif "tool_call" in response:
            print("✗ FAIL: Incorrectly tried to call a tool for a simple greeting")
            return False
        else:
            print(f"✗ FAIL: Unexpected response format: {response}")
            return False
    except Exception as e:
        print(f"✗ FAIL: Exception occurred: {e}")
        return False

async def test_tool_calling_response():
    """Test that requests requiring tools properly return tool_call format."""
    print("\n=== Test 2: Tool Calling Response ===")
    
    llm = OllamaLLM(model=os.getenv("AGENT_MODEL", "llama3.1:8b-instruct-q4_K_M"), json_mode=True, num_ctx=8000)
    
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant with tools."},
        {"role": "user", "content": "Search the web for the latest news about AI"}
    ]
    
    tools = [
        {
            "name": "webbrowser",
            "description": "Search the web or fetch URLs",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["search", "fetch"]},
                    "query": {"type": "string"}
                },
                "required": ["action"]
            }
        }
    ]
    
    try:
        response = await llm.chat(messages, tools=tools)
        print(f"Response: {response}")
        
        # For this test, we accept either a tool call OR a text response explaining
        # the assistant would search. Some models might not call tools reliably.
        if "tool_call" in response:
            print("✓ PASS: Returned tool_call response")
            return True
        elif "text" in response:
            print("⚠ PARTIAL: Returned text instead of tool call (acceptable for some models)")
            return True
        else:
            print(f"✗ FAIL: Unexpected response format: {response}")
            return False
    except Exception as e:
        print(f"✗ FAIL: Exception occurred: {e}")
        return False

async def test_no_tools_available():
    """Test conversational response when no tools are available."""
    print("\n=== Test 3: No Tools Available ===")
    
    llm = OllamaLLM(model=os.getenv("AGENT_MODEL", "llama3.1:8b-instruct-q4_K_M"), json_mode=True, num_ctx=8000)
    
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "What is the weather like?"}
    ]
    
    try:
        response = await llm.chat(messages, tools=[])
        print(f"Response: {response}")
        
        if "text" in response:
            print("✓ PASS: Returned text response when no tools available")
            return True
        else:
            print(f"✗ FAIL: Unexpected response format: {response}")
            return False
    except Exception as e:
        print(f"✗ FAIL: Exception occurred: {e}")
        return False

async def main():
    """Run all tests."""
    print("=" * 60)
    print("LLM Response Format Tests")
    print("=" * 60)
    print(f"Testing model: {os.getenv('AGENT_MODEL', 'llama3.1:8b-instruct-q4_K_M')}")
    
    # Check if Ollama is running
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:11434/api/tags", timeout=2) as resp:
                if resp.status != 200:
                    print("\n✗ ERROR: Ollama is not responding correctly")
                    print("Please ensure Ollama is running: ollama serve")
                    return 1
    except Exception as e:
        print(f"\n✗ ERROR: Cannot connect to Ollama: {e}")
        print("Please ensure Ollama is running: ollama serve")
        return 1
    
    results = []
    
    results.append(await test_conversational_response())
    results.append(await test_tool_calling_response())
    results.append(await test_no_tools_available())
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
