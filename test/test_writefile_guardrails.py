"""
Simple standalone test for WriteFileSmolTool guardrails logic.
Tests the core safety features without requiring smolagents.
"""
import os
import re


# Replicate the patterns from writefile_smol.py
ALLOWED_EXTENSIONS = {
    '.py', '.txt', '.md', '.csv', '.json', '.yaml', '.yml',
    '.html', '.css', '.js', '.xml', '.log', '.sh', '.bat',
    '.toml', '.ini', '.cfg', '.conf', '.rst', '.tex'
}

HARMFUL_PATTERNS = [
    r'os\.system\s*\(',
    r'subprocess\.',
    r'eval\s*\(',
    r'exec\s*\(',
    r'__import__\s*\(',
    r'os\.remove',
    r'os\.rmdir',
    r'os\.unlink',
    r'shutil\.rmtree',
    r'socket\.',
    r'urllib\.request',
    r'import\s+subprocess',
    r'from\s+subprocess',
    r'import\s+os\s*$',
    r'from\s+os\s+import',
]

SENSITIVE_PATTERNS = [
    r'password\s*=\s*["\']',
    r'api_key\s*=\s*["\']',
    r'secret\s*=\s*["\']',
    r'token\s*=\s*["\']',
    r'private_key\s*=\s*["\']',
]


def check_filename_safe(filename: str) -> tuple:
    """Verify filename is safe."""
    clean_name = os.path.basename(filename)
    if clean_name != filename:
        return False, f"Filename cannot contain path separators. Use '{clean_name}' instead."
    
    _, ext = os.path.splitext(clean_name)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
        return False, f"File extension '{ext}' not allowed. Allowed: {allowed}"
    
    return True, ""


def scan_content_safety(content: str, filename: str) -> tuple:
    """Scan content for harmful patterns and sensitive data."""
    warnings = []
    
    _, ext = os.path.splitext(filename)
    if ext == '.py':
        for pattern in HARMFUL_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                return False, f"Content contains potentially harmful pattern: {pattern}", []
    
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            warnings.append(f"Warning: Content may contain sensitive data matching pattern: {pattern}")
    
    return True, "", warnings


def test_filename_checks():
    """Test filename validation."""
    print("Testing filename validation...")
    
    # Valid filenames
    assert check_filename_safe("test.txt")[0] == True
    assert check_filename_safe("script.py")[0] == True
    assert check_filename_safe("data.json")[0] == True
    print("  ✓ Valid filenames accepted")
    
    # Invalid extension
    assert check_filename_safe("malware.exe")[0] == False
    print("  ✓ Invalid extension rejected")
    
    # Path traversal
    is_safe, msg = check_filename_safe("../../../etc/passwd")
    assert is_safe == False or "passwd" in msg
    print("  ✓ Path traversal detected")
    
    print()


def test_harmful_code_detection():
    """Test harmful code pattern detection."""
    print("Testing harmful code detection...")
    
    # Test os.system
    harmful1 = "import os\nos.system('rm -rf /')"
    is_safe, msg, _ = scan_content_safety(harmful1, "test.py")
    assert is_safe == False
    print("  ✓ os.system detected")
    
    # Test subprocess
    harmful2 = "import subprocess\nsubprocess.call(['ls'])"
    is_safe, msg, _ = scan_content_safety(harmful2, "test.py")
    assert is_safe == False
    print("  ✓ subprocess detected")
    
    # Test eval
    harmful3 = "result = eval(user_input)"
    is_safe, msg, _ = scan_content_safety(harmful3, "test.py")
    assert is_safe == False
    print("  ✓ eval detected")
    
    # Test exec
    harmful4 = "exec('print(\"hello\")')"
    is_safe, msg, _ = scan_content_safety(harmful4, "test.py")
    assert is_safe == False
    print("  ✓ exec detected")
    
    print()


def test_safe_code_allowed():
    """Test that safe code is allowed."""
    print("Testing safe code is allowed...")
    
    safe_code = """
def calculate_sum(a, b):
    return a + b

result = calculate_sum(5, 3)
print(f"Result: {result}")
"""
    is_safe, msg, warnings = scan_content_safety(safe_code, "test.py")
    assert is_safe == True
    print("  ✓ Safe Python code allowed")
    
    # Non-Python files should bypass Python checks
    is_safe, msg, warnings = scan_content_safety("import os\nos.system('test')", "test.txt")
    assert is_safe == True
    print("  ✓ Non-Python files bypass Python-specific checks")
    
    print()


def test_sensitive_data_warnings():
    """Test sensitive data pattern warnings."""
    print("Testing sensitive data warnings...")
    
    config = """
API_KEY = "sk-1234567890"
PASSWORD = "secret"
"""
    is_safe, msg, warnings = scan_content_safety(config, "config.py")
    assert is_safe == True  # Should be safe but with warnings
    assert len(warnings) > 0
    print(f"  ✓ Sensitive data warnings triggered: {len(warnings)} warnings")
    
    print()


def test_various_file_types():
    """Test that various file types are allowed."""
    print("Testing various file types...")
    
    types = [
        ("test.py", "print('hello')"),
        ("readme.md", "# Readme"),
        ("data.json", '{"key": "value"}'),
        ("config.yaml", "key: value"),
        ("style.css", "body { margin: 0; }"),
        ("script.js", "console.log('test');"),
    ]
    
    for filename, content in types:
        is_safe_fn, _ = check_filename_safe(filename)
        is_safe_content, _, _ = scan_content_safety(content, filename)
        assert is_safe_fn == True
        assert is_safe_content == True
        print(f"  ✓ {filename} allowed")
    
    print()


def main():
    """Run all tests."""
    print("\n=== WriteFileSmolTool Guardrails Tests ===\n")
    
    try:
        test_filename_checks()
        test_harmful_code_detection()
        test_safe_code_allowed()
        test_sensitive_data_warnings()
        test_various_file_types()
        
        print("✅ All guardrails tests passed!\n")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
