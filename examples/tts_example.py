#!/usr/bin/env python3
"""
Example script demonstrating NeuTTS-Air text-to-speech usage in Nayu AI.

Before running this script:
1. Install espeak: sudo apt install espeak (or equivalent for your OS)
2. Install dependencies: pip install -r requirements.txt
3. Set environment variables:
   export TTS_REF_AUDIO=/path/to/reference.wav  (or reference.pt for ONNX decoder)
   export TTS_REF_TEXT=/path/to/reference.txt (or the text content)

Note: When using ONNX decoder (default), you can use either:
  - Pre-encoded .pt files (fastest): export TTS_REF_AUDIO=/path/to/reference.pt
  - Raw .wav files (requires neucodec): export TTS_REF_AUDIO=/path/to/reference.wav

Usage:
    python examples/tts_example.py "Text to speak"
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.tools.speech import SpeechTool
from src.agents.state import SharedState


async def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/tts_example.py 'Text to speak'")
        print("\nExample:")
        print("  python examples/tts_example.py 'Hello, this is a test of NeuTTS-Air voice synthesis.'")
        print("\nMake sure to set TTS_REF_AUDIO and TTS_REF_TEXT environment variables.")
        sys.exit(1)
    
    text_to_speak = sys.argv[1]
    
    # Check environment variables
    ref_audio = os.getenv("TTS_REF_AUDIO")
    ref_text = os.getenv("TTS_REF_TEXT")
    
    if not ref_audio or not ref_text:
        print("⚠️  Warning: TTS_REF_AUDIO and/or TTS_REF_TEXT environment variables not set.")
        print("   TTS will not work without reference audio configuration.")
        print("\nSet them like this:")
        print("  export TTS_REF_AUDIO=/path/to/reference.wav")
        print("  export TTS_REF_TEXT=/path/to/reference.txt")
        print("\nOr provide text directly:")
        print('  export TTS_REF_TEXT="The transcript of your reference audio"')
        print("\nSee docs/TTS_SETUP.md for more information.")
        print("\nContinuing anyway (will print text instead)...")
        print()
    
    print(f"Initializing SpeechTool...")
    state = SharedState()
    speech_tool = SpeechTool(state)
    
    print(f"Converting text to speech: '{text_to_speak}'")
    result = await speech_tool.run(action="speak", text=text_to_speak)
    
    print(f"\nResult: {result['summary']}")
    
    if "out.wav" in result['summary']:
        print(f"\n✅ Audio generated successfully!")
        print(f"   Output file: out.wav")
        print(f"   You can play it with: aplay out.wav (Linux) or afplay out.wav (macOS)")
    else:
        print(f"\n⚠️  Audio not generated. Check the message above for details.")


if __name__ == "__main__":
    asyncio.run(main())
