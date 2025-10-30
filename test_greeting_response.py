#!/usr/bin/env python3
"""
Quick test to validate that simple greetings return conversational responses, not code.
This test can be run to verify the fix works correctly.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.llm.ollama_client import OllamaLLM

async def test_greeting():
    """Test that 'Hello' gets a conversational response without code generation."""
    print("Testing LLM response to 'Hello'...")
    print("=" * 60)
    
    llm = OllamaLLM(
        model=os.getenv("AGENT_MODEL", "llama3.1:8b-instruct-q4_K_M"),
        json_mode=True,
        num_ctx=8000
    )
    
    # Simulate the actual system prompt from main_agent.py
    system_prompt = """You are a helpful, friendly AI assistant. Your primary role is to chat naturally with users and help them with their requests.

RESPONSE FORMAT - You MUST respond using ONLY valid JSON in one of these formats:
1. For normal conversation (greetings, questions, general chat): {"text": "your conversational response"}
2. For using a tool (ONLY when truly needed): {"tool_call": {"name": "tool_name", "arguments": {...}}}

CRITICAL RULES:
- DEFAULT to conversation: For "Hello", "How are you", questions, etc. → use {"text": "..."}
- Use tools ONLY for specific tasks that require them (web search, code execution, memory operations)
- Output ONLY the JSON - no other text before or after
- Do NOT generate code, tests, examples, or documentation in your {"text": "..."} responses
- Be warm and conversational in your {"text": "..."} responses

WHEN TO USE EACH FORMAT:
- User: "Hello" → {"text": "Hello! How can I help you today?"}
- User: "What's the weather?" → {"text": "I don't have real-time weather data, but I can search the web if you'd like!"}
- User: "Search for Python tutorials" → {"tool_call": {"name": "webbrowser", "arguments": {"action": "search", "query": "Python tutorials"}}}"""
    
    # Create example tool specs
    tool_specs = [
        {
            "name": "webbrowser",
            "description": "Search the web or fetch URLs",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "query": {"type": "string"}
                }
            }
        }
    ]
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Hello"}
    ]
    
    try:
        response = await llm.chat(messages, tools=tool_specs)
        
        print(f"Response: {response}")
        print("=" * 60)
        
        # Validate the response
        if "text" in response:
            text = response["text"]
            print("✓ Response format: Conversational text (correct)")
            
            # Check for code patterns
            code_patterns = [
                "import ", "def ", "class ", "assert ", "public class",
                "@", "function ", "const ", "var ", "package "
            ]
            
            has_code = any(pattern in text for pattern in code_patterns)
            
            if has_code:
                print("✗ FAIL: Response contains code patterns")
                print(f"   Text: {text[:200]}")
                return False
            else:
                print("✓ Response content: No code generation (correct)")
                print(f"   Text: {text}")
                return True
        
        elif "tool_call" in response:
            print("✗ FAIL: Incorrectly tried to call a tool for 'Hello'")
            return False
        
        else:
            print(f"✗ FAIL: Unexpected response format")
            return False
            
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("\nChecking Ollama connection...")
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:11434/api/tags", timeout=2) as resp:
                if resp.status == 200:
                    print("✓ Ollama is running\n")
                else:
                    print("⚠ Warning: Ollama may not be responding correctly\n")
    except Exception as e:
        print(f"⚠ Warning: Cannot connect to Ollama: {e}")
        print("Please ensure Ollama is running: ollama serve\n")
    
    success = await test_greeting()
    
    if success:
        print("\n" + "=" * 60)
        print("✓ TEST PASSED: Agent responds conversationally to greetings")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("✗ TEST FAILED: Agent still generating inappropriate responses")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
