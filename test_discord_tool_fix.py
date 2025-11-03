#!/usr/bin/env python3
"""
Test to verify the Discord tool fix eliminates duplicate calls.

This test validates:
1. DiscordSmolTool is a direct Tool (not wrapping an agent)
2. The tool can be instantiated with a mock service
3. The tool's forward method can be called directly
4. No nested agent architecture exists
"""

from unittest.mock import Mock, AsyncMock
from src.agents.tools.discord_tool_smol import DiscordSmolTool


def test_discord_tool_structure():
    """Test that DiscordSmolTool has the correct structure."""
    from smolagents import Tool
    
    # Verify it's a direct Tool subclass
    assert issubclass(DiscordSmolTool, Tool)
    
    # Verify it has the required attributes
    assert hasattr(DiscordSmolTool, 'name')
    assert hasattr(DiscordSmolTool, 'description')
    assert hasattr(DiscordSmolTool, 'inputs')
    assert hasattr(DiscordSmolTool, 'output_type')
    assert hasattr(DiscordSmolTool, 'forward')
    
    print("✓ DiscordSmolTool structure is correct")


def test_discord_tool_instantiation():
    """Test that DiscordSmolTool can be instantiated with a mock service."""
    # Create a mock Discord service
    mock_service = Mock()
    mock_service.send_dm_target = AsyncMock()
    mock_service.send_channel_target = AsyncMock()
    
    # Instantiate the tool
    tool = DiscordSmolTool(mock_service)
    
    # Verify the tool has the service
    assert tool.discord_service is mock_service
    
    print("✓ DiscordSmolTool can be instantiated")


def test_discord_tool_forward():
    """Test that the forward method works and doesn't create nested agents."""
    # Create a mock Discord service
    mock_service = Mock()
    mock_service.send_dm_target = AsyncMock(return_value=None)
    mock_service.send_channel_target = AsyncMock(return_value=None)
    
    # Instantiate the tool
    tool = DiscordSmolTool(mock_service)
    
    # Call the forward method (this should NOT create a nested agent)
    result = tool.forward(
        action="dm",
        target="@testuser",
        message="Test message"
    )
    
    # Verify result is a string (the tool's response, not an agent's response)
    assert isinstance(result, str)
    assert "DM" in result  # Should mention DM in response
    
    # Verify no ToolCallingAgent was created
    # The tool should directly use the discord_service, not wrap it in an agent
    assert not hasattr(tool, 'discord_agent'), "Tool should not have a nested agent"
    
    print("✓ DiscordSmolTool.forward() works without nested agents")
    print(f"  Result: {result}")


def test_no_nested_agent_in_main_agent():
    """Verify that MainAgentSmol uses DiscordSmolTool directly, not DiscordAgentTool."""
    import inspect
    
    try:
        from src.agents.main_agent_smol import MainAgentSmol
    except ModuleNotFoundError as e:
        print(f"⚠ Skipping MainAgentSmol import test (missing dependency: {e})")
        # Fallback: check the source file directly
        with open("src/agents/main_agent_smol.py", "r") as f:
            source = f.read()
        
        # Find the add_discord_tool method
        method_start = source.find("def add_discord_tool")
        method_end = source.find("\n    def ", method_start + 1)
        method_source = source[method_start:method_end] if method_end > 0 else source[method_start:]
        
        # Verify it imports DiscordSmolTool, not DiscordAgentTool
        assert "DiscordSmolTool" in method_source, "Should import DiscordSmolTool"
        assert "DiscordAgentTool" not in method_source, "Should NOT import DiscordAgentTool"
        
        # Verify it doesn't create a ToolCallingAgent
        assert "ToolCallingAgent" not in method_source, "Should NOT create a ToolCallingAgent"
        
        print("✓ MainAgentSmol uses DiscordSmolTool directly (no nested agent) [verified from source]")
        return
    
    # Get the source code of add_discord_tool method
    source = inspect.getsource(MainAgentSmol.add_discord_tool)
    
    # Verify it imports DiscordSmolTool, not DiscordAgentTool
    assert "DiscordSmolTool" in source, "Should import DiscordSmolTool"
    assert "DiscordAgentTool" not in source, "Should NOT import DiscordAgentTool"
    
    # Verify it doesn't create a ToolCallingAgent
    assert "ToolCallingAgent" not in source, "Should NOT create a ToolCallingAgent"
    
    print("✓ MainAgentSmol uses DiscordSmolTool directly (no nested agent)")


def test_tool_description_clarity():
    """Test that the tool description is clear about its functionality."""
    description = DiscordSmolTool.description
    
    # Should mention both DM and channel capabilities
    assert "DM" in description or "direct message" in description.lower()
    assert "channel" in description.lower()
    
    # Should mention actions
    inputs = DiscordSmolTool.inputs
    assert inputs["action"]["enum"] == ["dm", "channel"]
    
    print("✓ Tool description is clear and complete")


if __name__ == "__main__":
    print("Testing Discord tool fix...\n")
    
    test_discord_tool_structure()
    test_discord_tool_instantiation()
    test_discord_tool_forward()
    test_no_nested_agent_in_main_agent()
    test_tool_description_clarity()
    
    print("\n" + "="*60)
    print("All tests passed! ✓")
    print("="*60)
    print("\nSummary:")
    print("- DiscordSmolTool is a direct Tool implementation")
    print("- No nested ToolCallingAgent architecture")
    print("- Tool can be called directly without creating duplicate final_answers")
    print("- MainAgentSmol correctly uses the direct tool")
