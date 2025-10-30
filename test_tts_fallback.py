#!/usr/bin/env python3
"""
Test script to demonstrate TTS fallback behavior.

This script tests the SpeechTool to verify that:
1. It initializes correctly when neutts-air is not installed
2. It prints fallback text when TTS is unavailable
3. Error messages are helpful and actionable
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    print("=" * 70)
    print("TTS Fallback Test")
    print("=" * 70)
    print()
    print("This test demonstrates the TTS fallback behavior when neutts-air")
    print("is not installed or unavailable.")
    print()
    
    try:
        from src.agents.state import SharedState
        from src.agents.tools.speech import SpeechTool
        
        print("Step 1: Initializing SpeechTool...")
        print("-" * 70)
        state = SharedState()
        speech = SpeechTool(state)
        print()
        
        print("Step 2: Checking TTS availability...")
        print("-" * 70)
        if speech.tts_available:
            print("✓ NeuTTS-Air is available!")
            print(f"  Reference audio: {speech.ref_audio_path or '(not configured)'}")
            print(f"  Reference text: {speech.ref_text[:50] if speech.ref_text else '(not configured)'}")
        else:
            print("ℹ NeuTTS-Air is not available")
            if speech.import_error:
                print(f"  Import error: {speech.import_error}")
            print("  Text-to-speech will fall back to printing text")
        print()
        
        print("Step 3: Testing speak action...")
        print("-" * 70)
        print("Expected: Text should be printed to console with [TTS FALLBACK] prefix")
        print()
        
        test_messages = [
            "Hello, this is a test of the text-to-speech system.",
            "The quick brown fox jumps over the lazy dog.",
            "Testing, one, two, three."
        ]
        
        for i, msg in enumerate(test_messages, 1):
            print(f"Test {i}: Speaking: \"{msg}\"")
            result = await speech.run(action="speak", text=msg)
            print(f"Result: {result['summary']}")
            print()
        
        print("=" * 70)
        print("✓ Test completed successfully!")
        print("=" * 70)
        print()
        print("If neutts-air is not installed, you should see:")
        print("  1. [TTS FALLBACK] messages printed above")
        print("  2. Helpful error messages about installation")
        print()
        print("To install neutts-air, run:")
        print("  bash scripts/install_neutts_air.sh")
        print()
        print("Or see docs/TTS_SETUP.md for detailed instructions.")
        print()
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
