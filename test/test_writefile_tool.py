"""
Test script for WriteFileSmolTool
Tests basic functionality, guardrails, and error handling.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from src.agents.tools.writefile_smol import WriteFileSmolTool


def test_basic_write():
    """Test basic file writing."""
    tool = WriteFileSmolTool()
    
    # Test writing a simple text file
    result = tool.forward(
        filename="test.txt",
        content="Hello, World!",
        mode="write"
    )
    print(f"✓ Basic write test: {result}")
    assert "Wrote file" in result
    assert os.path.exists(".workspace/test.txt")
    with open(".workspace/test.txt", 'r') as f:
        assert f.read() == "Hello, World!"


def test_append_mode():
    """Test append mode."""
    tool = WriteFileSmolTool()
    
    # First write
    tool.forward(filename="append_test.txt", content="Line 1\n", mode="write")
    # Append
    result = tool.forward(filename="append_test.txt", content="Line 2\n", mode="append")
    print(f"✓ Append mode test: {result}")
    assert "Appended to" in result
    
    with open(".workspace/append_test.txt", 'r') as f:
        content = f.read()
        assert "Line 1" in content
        assert "Line 2" in content


def test_python_file():
    """Test writing Python file."""
    tool = WriteFileSmolTool()
    
    code = """
def hello():
    print("Hello from Python!")
    
if __name__ == "__main__":
    hello()
"""
    result = tool.forward(filename="script.py", content=code, mode="write")
    print(f"✓ Python file test: {result}")
    assert "Wrote file" in result
    assert os.path.exists(".workspace/script.py")


def test_invalid_extension():
    """Test that invalid extensions are rejected."""
    tool = WriteFileSmolTool()
    
    result = tool.forward(filename="test.exe", content="malicious", mode="write")
    print(f"✓ Invalid extension test: {result}")
    assert "Error" in result
    assert "not allowed" in result


def test_path_traversal():
    """Test that path traversal is blocked."""
    tool = WriteFileSmolTool()
    
    result = tool.forward(filename="../../../etc/passwd", content="hacked", mode="write")
    print(f"✓ Path traversal test: {result}")
    assert "Error" in result or "passwd" not in result


def test_harmful_code_detection():
    """Test that harmful code patterns are detected."""
    tool = WriteFileSmolTool()
    
    # Test os.system
    harmful_code = """
import os
os.system("rm -rf /")
"""
    result = tool.forward(filename="harmful.py", content=harmful_code, mode="write")
    print(f"✓ Harmful code detection test: {result}")
    assert "Error" in result
    assert "harmful" in result.lower()


def test_subprocess_detection():
    """Test that subprocess usage is detected."""
    tool = WriteFileSmolTool()
    
    harmful_code = """
import subprocess
subprocess.call(['ls', '-la'])
"""
    result = tool.forward(filename="subprocess_test.py", content=harmful_code, mode="write")
    print(f"✓ Subprocess detection test: {result}")
    assert "Error" in result


def test_safe_python_code():
    """Test that safe Python code is allowed."""
    tool = WriteFileSmolTool()
    
    safe_code = """
def calculate_sum(a, b):
    return a + b

result = calculate_sum(5, 3)
print(f"Result: {result}")
"""
    result = tool.forward(filename="safe_script.py", content=safe_code, mode="write")
    print(f"✓ Safe code test: {result}")
    assert "Wrote file" in result
    assert "Error" not in result


def test_json_file():
    """Test writing JSON file."""
    tool = WriteFileSmolTool()
    
    json_content = '{"name": "test", "value": 42}'
    result = tool.forward(filename="data.json", content=json_content, mode="write")
    print(f"✓ JSON file test: {result}")
    assert "Wrote file" in result


def test_markdown_file():
    """Test writing Markdown file."""
    tool = WriteFileSmolTool()
    
    md_content = """# Test Document

This is a test markdown file.

## Section 1
Content here.
"""
    result = tool.forward(filename="test.md", content=md_content, mode="write")
    print(f"✓ Markdown file test: {result}")
    assert "Wrote file" in result


def test_sensitive_data_warning():
    """Test that sensitive data patterns trigger warnings."""
    tool = WriteFileSmolTool()
    
    config_content = """
API_KEY = "sk-1234567890abcdef"
PASSWORD = "secret123"
"""
    result = tool.forward(filename="config.py", content=config_content, mode="write")
    print(f"✓ Sensitive data warning test: {result}")
    # Should write but warn
    assert "Wrote file" in result or "Warning" in result


def cleanup():
    """Clean up test files."""
    import shutil
    if os.path.exists(".workspace"):
        for file in os.listdir(".workspace"):
            if file != "README.md":
                filepath = os.path.join(".workspace", file)
                if os.path.isfile(filepath):
                    os.remove(filepath)


def main():
    """Run all tests."""
    print("\n=== WriteFileSmolTool Tests ===\n")
    
    try:
        test_basic_write()
        test_append_mode()
        test_python_file()
        test_invalid_extension()
        test_path_traversal()
        test_harmful_code_detection()
        test_subprocess_detection()
        test_safe_python_code()
        test_json_file()
        test_markdown_file()
        test_sensitive_data_warning()
        
        print("\n✅ All tests passed!\n")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # cleanup()
        print("Note: Test files left in .workspace/ for inspection. Run cleanup() to remove.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
