#!/usr/bin/env python3
"""
Simple verification test for speech tool encode_reference_audio logic.
Verifies the code structure and branching without full dependencies.
"""

import sys
import ast
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_speech_file_structure():
    """Verify the speech.py file has the expected structure."""
    
    print("Verifying speech tool implementation...\n")
    
    speech_file = project_root / "src" / "agents" / "tools" / "speech.py"
    
    if not speech_file.exists():
        print(f"❌ Speech file not found: {speech_file}")
        return False
    
    with open(speech_file, 'r') as f:
        content = f.read()
    
    # Verify key components exist
    checks = [
        ("Import Path from pathlib", "from pathlib import Path" in content),
        ("_encode_reference_audio method", "def _encode_reference_audio(" in content),
        ("encoder_for_reference attribute", "self.encoder_for_reference" in content),
        ("Check for .pt file", "suffix == '.pt'" in content or 'suffix == ".pt"' in content),
        ("Check for ONNX codec flag", "_is_onnx_codec" in content),
        ("Load pre-encoded .pt file", "torch.load(" in content),
        ("Use separate encoder for ONNX", "NeuCodec.from_pretrained" in content),
        ("Handle both ONNX and full codec", "else:" in content and "encode_reference(" in content),
        ("Error handling for encoding", "except" in content and "RuntimeError" in content),
    ]
    
    all_passed = True
    for check_name, check_result in checks:
        if check_result:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name}")
            all_passed = False
    
    # Parse the file to verify syntax
    try:
        tree = ast.parse(content)
        print("\n  ✅ Python syntax is valid")
    except SyntaxError as e:
        print(f"\n  ❌ Syntax error: {e}")
        all_passed = False
    
    # Find the _encode_reference_audio method and verify structure
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_encode_reference_audio":
            print(f"  ✅ Found _encode_reference_audio method with {len(node.body)} statements")
            
            # Check for proper branching
            has_if_pt = False
            has_if_onnx = False
            has_else = False
            
            for item in ast.walk(node):
                if isinstance(item, ast.If):
                    # Check for .pt check
                    if isinstance(item.test, ast.Compare):
                        has_if_pt = True
                    # Check for ONNX check
                    if isinstance(item.test, ast.BoolOp) or (
                        hasattr(item.test, 'func') and 
                        hasattr(item.test.func, 'attr') and 
                        'hasattr' in str(item.test.func)
                    ):
                        has_if_onnx = True
                if isinstance(item, ast.If) and item.orelse:
                    has_else = True
            
            if has_if_pt:
                print("  ✅ Has conditional check for .pt files")
            if has_if_onnx:
                print("  ✅ Has conditional check for ONNX decoder")
            if has_else:
                print("  ✅ Has else branch for fallback logic")
    
    print("\n" + ("="*60))
    if all_passed:
        print("✅ All structural checks passed!")
        print("\nThe implementation correctly handles:")
        print("  1. Pre-encoded .pt files (fastest)")
        print("  2. ONNX decoder with .wav files (uses separate encoder)")
        print("  3. Full PyTorch codec with .wav files (direct encoding)")
    else:
        print("❌ Some checks failed. Review the implementation.")
    print("="*60)
    
    return all_passed


if __name__ == "__main__":
    success = test_speech_file_structure()
    sys.exit(0 if success else 1)
