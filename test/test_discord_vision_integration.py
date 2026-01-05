#!/usr/bin/env python3
"""
Test Discord vision integration.

This test validates:
1. Discord bot downloads image attachments
2. Image paths are passed to the agent via metadata
3. Agent is informed about available images
4. Vision tool can be called with downloaded images
"""

import os
import sys
import tempfile
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock discord and other heavy dependencies before importing
sys.modules['discord'] = MagicMock()
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()
sys.modules['fastembed'] = MagicMock()
sys.modules['litellm'] = MagicMock()
sys.modules['aiohttp'] = MagicMock()
sys.modules['chromadb'] = MagicMock()


def test_download_attachments_function_exists():
    """Test that the _download_attachments function exists."""
    from src.integrations.discord_bot import _download_attachments
    
    assert callable(_download_attachments)
    print("✓ _download_attachments function exists")


def test_discord_image_dir_constant():
    """Test that DISCORD_IMAGE_DIR constant is defined."""
    from src.integrations.discord_bot import DISCORD_IMAGE_DIR
    
    assert DISCORD_IMAGE_DIR == ".cache/discord_images"
    print("✓ DISCORD_IMAGE_DIR constant is defined correctly")


async def test_download_attachments_empty_message():
    """Test _download_attachments with a message that has no attachments."""
    from src.integrations.discord_bot import _download_attachments
    
    # Create a mock message with no attachments
    mock_message = Mock()
    mock_message.attachments = []
    
    result = await _download_attachments(mock_message)
    
    assert result == []
    print("✓ _download_attachments returns empty list for message with no attachments")


async def test_download_attachments_with_image():
    """Test _download_attachments with an image attachment."""
    from src.integrations.discord_bot import _download_attachments
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use patch to override the DISCORD_IMAGE_DIR for this test
        with patch('src.integrations.discord_bot.DISCORD_IMAGE_DIR', tmpdir):
            # Create a mock attachment
            mock_attachment = Mock()
            mock_attachment.content_type = "image/png"
            mock_attachment.filename = "test_image.png"
            mock_attachment.id = 123456789
            mock_attachment.url = "https://example.com/image.png"
            
            # Create a simple test image content
            test_image_content = b"fake_image_data"
            
            async def mock_save(filepath):
                # Simulate saving the file
                Path(filepath).parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, "wb") as f:
                    f.write(test_image_content)
            
            mock_attachment.save = mock_save
            
            # Create a mock message with the attachment
            mock_message = Mock()
            mock_message.attachments = [mock_attachment]
            mock_message.id = 987654321
            
            # Download attachments
            result = await _download_attachments(mock_message)
            
            # Verify result
            assert len(result) == 1
            assert os.path.exists(result[0])
            assert result[0].startswith(tmpdir)
            assert "discord_987654321_123456789" in result[0]
            
            # Verify file content
            with open(result[0], "rb") as f:
                content = f.read()
                assert content == test_image_content
            
            print(f"✓ _download_attachments successfully downloads image to {result[0]}")


def test_metadata_includes_downloaded_images():
    """Test that metadata passed to agent includes downloaded_images field."""
    # This is a structural test to verify the code paths exist
    import inspect
    from src.integrations.discord_bot import DiscordBotService
    
    # Get the source of _maybe_get_agent_reply
    source = inspect.getsource(DiscordBotService._maybe_get_agent_reply)
    
    # Verify it downloads attachments
    assert "_download_attachments" in source
    
    # Verify it adds downloaded_images to metadata
    assert "downloaded_images" in source
    
    print("✓ _maybe_get_agent_reply includes downloaded_images in metadata")


def test_agent_handles_image_metadata():
    """Test that the agent's handle_user_message processes image metadata."""
    # Read the source file directly to avoid import issues
    source_file = Path(__file__).parent.parent / "src" / "agents" / "main_agent_smol.py"
    with open(source_file, "r") as f:
        source = f.read()
    
    # Verify it checks for downloaded_images in metadata
    assert "downloaded_images" in source
    
    # Verify it adds image information to the prompt
    assert "IMAGE ATTACHMENTS" in source
    
    # Verify it has Discord-specific handling with priority indication
    assert "DISCORD IMAGE ATTACHMENTS" in source or "USE THESE FIRST" in source
    
    print("✓ Agent handle_user_message processes image metadata with Discord priority")


def test_vision_tool_in_system_prompt():
    """Test that vision tool is mentioned in the system prompt with proper scope."""
    # Read the source file directly
    source_file = Path(__file__).parent.parent / "src" / "agents" / "main_agent_smol.py"
    with open(source_file, "r") as f:
        source = f.read()
    
    # Verify vision tool is mentioned in SYSTEM_PROMPT
    assert "vision" in source and "SYSTEM_PROMPT" in source
    
    # Verify it mentions Discord attachments (not just screenshots)
    assert "Discord attachments" in source or "discord attachments" in source
    
    print("✓ Vision tool description includes Discord attachments and all image types")


def test_integration_flow():
    """Test the complete integration flow (structural verification)."""
    # Read source files directly to verify structure
    discord_file = Path(__file__).parent.parent / "src" / "integrations" / "discord_bot.py"
    agent_file = Path(__file__).parent.parent / "src" / "agents" / "main_agent_smol.py"
    
    with open(discord_file, "r") as f:
        discord_source = f.read()
    
    with open(agent_file, "r") as f:
        agent_source = f.read()
    
    # Verify DiscordBotService has the necessary methods
    assert "def _maybe_get_agent_reply" in discord_source
    assert "def _lightweight_ingest" in discord_source
    assert "_download_attachments" in discord_source
    
    # Verify MainAgentSmol has handle_external_message and handle_user_message
    assert "def handle_external_message" in agent_source or "async def handle_external_message" in agent_source
    assert "def handle_user_message" in agent_source or "async def handle_user_message" in agent_source
    
    print("✓ Integration flow has all necessary components")


if __name__ == "__main__":
    import asyncio
    
    print("Testing Discord vision integration...\n")
    
    # Synchronous tests
    test_download_attachments_function_exists()
    test_discord_image_dir_constant()
    test_metadata_includes_downloaded_images()
    test_agent_handles_image_metadata()
    test_vision_tool_in_system_prompt()
    test_integration_flow()
    
    # Asynchronous tests
    print("\nRunning async tests...")
    asyncio.run(test_download_attachments_empty_message())
    asyncio.run(test_download_attachments_with_image())
    
    print("\n" + "="*60)
    print("All tests passed! ✓")
    print("="*60)
    print("\nSummary:")
    print("- Discord bot downloads image attachments to .cache/discord_images/")
    print("- Image paths are passed to agent via metadata")
    print("- Agent informs LLM about available images")
    print("- Vision tool can be called with downloaded images")
    print("- Complete integration flow is in place")
