"""
Integration test to verify WriteFileTool is properly integrated into main agent.
This tests that the tool can be imported and initialized without errors.
"""
import sys
import os

# Mock smolagents to avoid dependency issues
class MockTool:
    pass

sys.modules['smolagents'] = type(sys)('smolagents')
sys.modules['smolagents'].Tool = MockTool

# Now we can import
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from src.agents.tools.writefile_smol import WriteFileSmolTool


def test_tool_initialization():
    """Test that WriteFileSmolTool can be initialized."""
    print("Testing WriteFileTool initialization...")
    
    tool = WriteFileSmolTool()
    
    # Check attributes
    assert hasattr(tool, 'name'), "Tool should have 'name' attribute"
    assert hasattr(tool, 'description'), "Tool should have 'description' attribute"
    assert hasattr(tool, 'inputs'), "Tool should have 'inputs' attribute"
    assert hasattr(tool, 'forward'), "Tool should have 'forward' method"
    
    assert tool.name == "write_file", f"Tool name should be 'write_file', got '{tool.name}'"
    print(f"  ✓ Tool name: {tool.name}")
    
    assert "write_file" in tool.description.lower() or "file" in tool.description.lower()
    print(f"  ✓ Tool description: {tool.description[:60]}...")
    
    # Check inputs structure
    assert "filename" in tool.inputs, "Tool should have 'filename' input"
    assert "content" in tool.inputs, "Tool should have 'content' input"
    assert "mode" in tool.inputs, "Tool should have 'mode' input"
    print(f"  ✓ Tool inputs defined: {list(tool.inputs.keys())}")
    
    # Check workspace directory was created
    assert os.path.exists(tool.workspace_dir), "Workspace directory should exist"
    print(f"  ✓ Workspace directory: {tool.workspace_dir}")
    
    print()


def test_tool_execution():
    """Test that the tool can execute basic operations."""
    print("Testing WriteFileTool execution...")
    
    tool = WriteFileSmolTool()
    
    # Test basic write
    result = tool.forward(
        filename="integration_test.txt",
        content="Integration test content",
        mode="write"
    )
    
    assert "Wrote file" in result or "Error" not in result, f"Expected success, got: {result}"
    print(f"  ✓ Write operation: {result[:80]}")
    
    # Verify file exists
    filepath = os.path.join(tool.workspace_dir, "integration_test.txt")
    assert os.path.exists(filepath), "File should have been created"
    print(f"  ✓ File created: {filepath}")
    
    # Clean up
    os.remove(filepath)
    print(f"  ✓ Cleanup successful")
    
    print()


def test_tool_metadata():
    """Test tool metadata for smolagents compatibility."""
    print("Testing tool metadata...")
    
    tool = WriteFileSmolTool()
    
    # Check output_type
    assert hasattr(tool, 'output_type'), "Tool should have 'output_type' attribute"
    assert tool.output_type == "string", "Output type should be 'string'"
    print(f"  ✓ Output type: {tool.output_type}")
    
    # Check inputs structure matches smolagents format
    for input_name, input_spec in tool.inputs.items():
        assert "type" in input_spec, f"Input '{input_name}' should have 'type'"
        assert "description" in input_spec, f"Input '{input_name}' should have 'description'"
        print(f"  ✓ Input '{input_name}': {input_spec['type']}")
    
    print()


def main():
    """Run all integration tests."""
    print("\n=== WriteFileTool Integration Tests ===\n")
    
    try:
        test_tool_initialization()
        test_tool_execution()
        test_tool_metadata()
        
        print("✅ All integration tests passed!\n")
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
    sys.exit(main())
