#!/usr/bin/env python3
"""
Helper script to pre-encode reference audio for use with ONNX decoder.

This script creates a .pt file containing encoded reference audio codes
that can be used directly with the ONNX decoder, avoiding the need to
load the full codec at runtime.

Usage:
    python examples/encode_reference.py input.wav output.pt

Example:
    python examples/encode_reference.py samples/dave.wav samples/dave.pt
"""

import sys
import torch
from pathlib import Path


def encode_reference_audio(input_path: str, output_path: str):
    """Encode reference audio and save to .pt file."""
    
    try:
        from neucodec import NeuCodec
        import librosa
    except ImportError as e:
        print(f"❌ Error: Required packages not installed")
        print(f"   Install with: pip install neucodec librosa")
        print(f"   Error details: {e}")
        sys.exit(1)
    
    input_file = Path(input_path)
    output_file = Path(output_path)
    
    if not input_file.exists():
        print(f"❌ Error: Input file not found: {input_path}")
        sys.exit(1)
    
    if output_file.exists():
        response = input(f"⚠️  Output file already exists: {output_path}\n   Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            sys.exit(0)
    
    print(f"📥 Loading audio from {input_path}...")
    try:
        wav, sr = librosa.load(input_path, sr=16000, mono=True)
        print(f"   Audio loaded: {len(wav)/sr:.2f} seconds at {sr} Hz")
    except Exception as e:
        print(f"❌ Error loading audio: {e}")
        sys.exit(1)
    
    print(f"🔧 Loading NeuCodec encoder...")
    try:
        codec = NeuCodec.from_pretrained("neuphonic/neucodec")
        codec.eval()
    except Exception as e:
        print(f"❌ Error loading codec: {e}")
        sys.exit(1)
    
    print(f"🎵 Encoding audio...")
    try:
        wav_tensor = torch.from_numpy(wav).float().unsqueeze(0).unsqueeze(0)  # [1, 1, T]
        with torch.no_grad():
            ref_codes = codec.encode_code(audio_or_path=wav_tensor).squeeze(0).squeeze(0)
        print(f"   Encoded to {ref_codes.shape[0]} codes")
    except Exception as e:
        print(f"❌ Error encoding audio: {e}")
        sys.exit(1)
    
    print(f"💾 Saving to {output_path}...")
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        torch.save(ref_codes, output_path)
        file_size = output_file.stat().st_size
        print(f"   Saved ({file_size} bytes)")
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        sys.exit(1)
    
    print(f"\n✅ Success! Reference audio encoded.")
    print(f"\nYou can now use the encoded reference:")
    print(f"   export TTS_REF_AUDIO={output_path}")
    print(f"\nOr in your code:")
    print(f"   speech_tool = SpeechTool(state, tts_ref_audio='{output_path}', tts_ref_text='...')")


def main():
    if len(sys.argv) != 3:
        print("Usage: python examples/encode_reference.py INPUT.wav OUTPUT.pt")
        print("\nExample:")
        print("  python examples/encode_reference.py samples/dave.wav samples/dave.pt")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    if not output_path.endswith('.pt'):
        print("⚠️  Warning: Output file should have .pt extension")
        response = input("   Continue anyway? [y/N]: ")
        if response.lower() != 'y':
            sys.exit(0)
    
    encode_reference_audio(input_path, output_path)


if __name__ == "__main__":
    main()
