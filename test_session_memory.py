#!/usr/bin/env python3
"""
Test script for session memory functionality.
Tests session persistence, rolling window, summaries, and working set updates.
"""
import sys
import os
import time
import tempfile
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.memory.session_manager import SessionManager, Message, WorkingSet


def test_session_creation():
    """Test creating and retrieving sessions."""
    print("\n1. Testing session creation and retrieval...")
    
    # Create temp directory for testing
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = SessionManager(session_dir=temp_dir, max_cache_size=2)
        
        # Create a session
        session = manager.get_session("test-session-1")
        assert session.session_id == "test-session-1"
        assert len(session.messages) == 0
        
        # Retrieve same session
        session2 = manager.get_session("test-session-1")
        assert session2.session_id == "test-session-1"
        assert session is session2  # Should be same object from cache
        
        print("   ✓ Session creation and retrieval works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_message_persistence():
    """Test adding messages and persistence."""
    print("\n2. Testing message persistence...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = SessionManager(session_dir=temp_dir, max_cache_size=2)
        
        # Add some messages
        manager.add_message("test-session-2", "user", "Hello, how are you?")
        manager.add_message("test-session-2", "assistant", "I'm doing well, thanks!")
        manager.add_message("test-session-2", "user", "Can you help me with something?")
        
        # Check messages were added
        session = manager.get_session("test-session-2")
        assert len(session.messages) == 3
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "Hello, how are you?"
        assert session.messages[1].role == "assistant"
        assert session.turn_count == 2  # Two user turns
        
        # Check persistence by creating new manager
        manager2 = SessionManager(session_dir=temp_dir)
        session2 = manager2.get_session("test-session-2")
        assert len(session2.messages) == 3
        assert session2.messages[0].content == "Hello, how are you?"
        
        print("   ✓ Message persistence works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_rolling_window():
    """Test rolling window truncation."""
    print("\n3. Testing rolling window truncation...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = SessionManager(
            session_dir=temp_dir,
            max_messages=5,
            max_tokens=100  # Very small for testing
        )
        
        # Add many messages
        for i in range(10):
            manager.add_message("test-session-3", "user", f"Message {i}")
            manager.add_message("test-session-3", "assistant", f"Response {i}")
        
        # Check that messages were truncated
        session = manager.get_session("test-session-3")
        assert len(session.messages) <= 5, f"Expected <= 5 messages, got {len(session.messages)}"
        
        # Check that most recent messages are kept
        assert "Message 9" in session.messages[-2].content or "Message 8" in session.messages[-2].content
        
        print("   ✓ Rolling window truncation works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_summary_generation():
    """Test automatic summary generation."""
    print("\n4. Testing summary generation...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = SessionManager(
            session_dir=temp_dir,
            summary_interval=3  # Generate summary every 3 turns
        )
        
        # Add messages to trigger summary
        manager.add_message("test-session-4", "user", "What's the weather?")
        manager.add_message("test-session-4", "assistant", "It's sunny.")
        manager.add_message("test-session-4", "user", "Tell me a joke.")
        manager.add_message("test-session-4", "assistant", "Why did the chicken cross the road?")
        manager.add_message("test-session-4", "user", "Open a file.")
        manager.add_message("test-session-4", "assistant", "Which file?")
        
        # Check that summary was generated
        session = manager.get_session("test-session-4")
        assert session.summary != "", "Summary should be generated"
        assert "Recent topics:" in session.summary or len(session.summary) > 0
        
        print(f"   ✓ Summary generation works: '{session.summary}'")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_working_set():
    """Test working set updates."""
    print("\n5. Testing working set updates...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = SessionManager(session_dir=temp_dir)
        
        # Update working set
        manager.update_working_set(
            "test-session-5",
            task_info={"id": "task-1", "type": "file_operation", "outcome": "success"},
            artifacts={"last_file": "/tmp/test.txt", "last_url": "https://example.com"},
            env_context={"project_root": "/home/user/project"}
        )
        
        # Get context
        summary, working_set_context, messages = manager.get_context("test-session-5")
        
        assert "last_file=/tmp/test.txt" in working_set_context
        assert "last_url=https://example.com" in working_set_context
        assert "project_root=/home/user/project" in working_set_context
        
        print(f"   ✓ Working set updates work: '{working_set_context}'")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_session_reset():
    """Test session reset functionality."""
    print("\n6. Testing session reset...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = SessionManager(session_dir=temp_dir)
        
        # Add messages
        manager.add_message("test-session-6", "user", "Hello")
        manager.add_message("test-session-6", "assistant", "Hi there")
        
        # Verify messages exist
        session = manager.get_session("test-session-6")
        assert len(session.messages) == 2
        
        # Reset session
        manager.reset_session("test-session-6")
        
        # Verify session is cleared
        session = manager.get_session("test-session-6")
        assert len(session.messages) == 0
        assert session.summary == ""
        
        print("   ✓ Session reset works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_context_assembly():
    """Test context assembly for LLM prompts."""
    print("\n7. Testing context assembly...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = SessionManager(session_dir=temp_dir)
        
        # Add conversation
        manager.add_message("test-session-7", "user", "Open the file report.txt")
        manager.add_message("test-session-7", "assistant", "I've opened report.txt")
        manager.add_message("test-session-7", "user", "Now edit it")
        
        # Update working set
        manager.update_working_set(
            "test-session-7",
            artifacts={"last_file": "report.txt"}
        )
        
        # Get context
        summary, working_set_context, messages = manager.get_context("test-session-7")
        
        # Verify context contains relevant information
        assert len(messages) == 3
        assert messages[-1].content == "Now edit it"
        assert "last_file=report.txt" in working_set_context
        
        print("   ✓ Context assembly works correctly")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Session Memory Implementation")
    print("=" * 60)
    
    tests = [
        test_session_creation,
        test_message_persistence,
        test_rolling_window,
        test_summary_generation,
        test_working_set,
        test_session_reset,
        test_context_assembly,
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print(f"✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
