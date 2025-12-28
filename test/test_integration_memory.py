#!/usr/bin/env python3
"""
Integration test for session memory with the main agent.
This simulates a conversation to verify context preservation.
"""
import sys
import os
import asyncio
import tempfile
import shutil

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.state import SharedState
from src.agents.core.events import EventBus
from src.agents.core.registry import ToolRegistry
from src.agents.core.store import SQLiteStore
from src.agents.notify.notifier import Notifier
from src.agents.memory.session_manager import SessionManager


async def test_session_integration():
    """Test that session manager integrates properly with the agent workflow."""
    print("=" * 60)
    print("Integration Test: Session Memory with Agent Flow")
    print("=" * 60)
    
    # Create temporary directories
    temp_cache = tempfile.mkdtemp()
    temp_sessions = tempfile.mkdtemp()
    
    try:
        # Initialize core components (minimal setup)
        state = SharedState()
        store = SQLiteStore(path=os.path.join(temp_cache, "test.db"))
        bus = EventBus(store=store)
        registry = ToolRegistry(store=store)
        notifier = Notifier(speech_tool=None, voice_enabled=False, speak_on_error=False)
        
        # Initialize session manager
        session_manager = SessionManager(session_dir=temp_sessions)
        
        print("\n1. Testing session initialization...")
        session_id = "test-integration-session"
        
        # Simulate conversation flow
        print("\n2. Simulating conversation...")
        
        # Turn 1
        user_msg_1 = "Open the file report.txt"
        session_manager.add_message(session_id, "user", user_msg_1)
        
        # Simulate getting context
        summary, working_set, messages = session_manager.get_context(session_id)
        print(f"   Turn 1 - User: {user_msg_1}")
        print(f"   Messages in session: {len(messages)}")
        
        # Simulate assistant response
        assistant_msg_1 = "I've opened report.txt for you."
        session_manager.add_message(session_id, "assistant", assistant_msg_1)
        
        # Update working set with artifact
        session_manager.update_working_set(
            session_id,
            task_info={"id": "task-1", "type": "file_open", "outcome": "success"},
            artifacts={"last_file": "report.txt"}
        )
        print(f"   Turn 1 - Assistant: {assistant_msg_1}")
        
        # Turn 2 - Reference to "that file"
        user_msg_2 = "Can you edit that file?"
        session_manager.add_message(session_id, "user", user_msg_2)
        
        # Get context again - should include previous conversation
        summary, working_set, messages = session_manager.get_context(session_id)
        print(f"\n   Turn 2 - User: {user_msg_2}")
        print(f"   Messages in session: {len(messages)}")
        print(f"   Working set: {working_set}")
        
        # Verify context contains reference to previous file
        assert "last_file=report.txt" in working_set, "Working set should contain last_file"
        assert len(messages) >= 3, "Should have at least 3 messages"
        
        # Turn 3 - Continue conversation
        assistant_msg_2 = "Sure, I can edit report.txt. What changes would you like?"
        session_manager.add_message(session_id, "assistant", assistant_msg_2)
        print(f"   Turn 2 - Assistant: {assistant_msg_2}")
        
        # Turn 4
        user_msg_3 = "Add a conclusion section"
        session_manager.add_message(session_id, "user", user_msg_3)
        print(f"\n   Turn 3 - User: {user_msg_3}")
        
        # Final context check
        summary, working_set, messages = session_manager.get_context(session_id)
        print(f"   Final message count: {len(messages)}")
        print(f"   Turn count: {session_manager.get_session(session_id).turn_count}")
        
        # Verify conversation continuity
        assert len(messages) >= 5, "Should have at least 5 messages"
        assert session_manager.get_session(session_id).turn_count == 3, "Should have 3 user turns"
        
        print("\n3. Testing session persistence...")
        # Flush to disk
        session_manager.flush_cache()
        
        # Create new manager and verify persistence
        session_manager2 = SessionManager(session_dir=temp_sessions)
        summary2, working_set2, messages2 = session_manager2.get_context(session_id)
        
        assert len(messages2) == len(messages), "Persisted messages should match"
        assert working_set2 == working_set, "Persisted working set should match"
        print("   ✓ Session persisted correctly")
        
        print("\n4. Testing session reset...")
        session_manager2.reset_session(session_id)
        summary3, working_set3, messages3 = session_manager2.get_context(session_id)
        
        assert len(messages3) == 0, "Messages should be cleared after reset"
        assert working_set3 == "", "Working set should be cleared after reset"
        print("   ✓ Session reset works correctly")
        
        print("\n" + "=" * 60)
        print("✓ Integration test passed!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        shutil.rmtree(temp_cache)
        shutil.rmtree(temp_sessions)
        store.close()


async def test_context_prompt_assembly():
    """Test that context is properly assembled for LLM prompts."""
    print("\n" + "=" * 60)
    print("Integration Test: Context Prompt Assembly")
    print("=" * 60)
    
    temp_sessions = tempfile.mkdtemp()
    
    try:
        session_manager = SessionManager(session_dir=temp_sessions)
        session_id = "test-prompt-assembly"
        
        # Build a conversation
        session_manager.add_message(session_id, "user", "Search for Python tutorials")
        session_manager.add_message(session_id, "assistant", "I found some Python tutorials.")
        session_manager.update_working_set(
            session_id,
            artifacts={"last_url": "https://python.org/tutorial"}
        )
        
        session_manager.add_message(session_id, "user", "Open that URL")
        
        # Get context
        summary, working_set, messages = session_manager.get_context(session_id)
        
        # Simulate prompt assembly (like in main_agent.py)
        conversation_history = ""
        if messages:
            history_lines = []
            for msg in messages[-10:]:
                role_label = "User" if msg.role == "user" else "Assistant"
                history_lines.append(f"{role_label}: {msg.content}")
            conversation_history = "\n".join(history_lines)
        
        print("\nAssembled Prompt Context:")
        print("-" * 60)
        print("WORKING SET:")
        print(working_set)
        print("\nCONVERSATION HISTORY:")
        print(conversation_history)
        print("-" * 60)
        
        # Verify the context contains necessary info for resolving "that URL"
        assert "last_url=https://python.org/tutorial" in working_set
        assert "Open that URL" in conversation_history
        assert "Search for Python tutorials" in conversation_history
        
        print("\n✓ Context prompt assembly test passed!")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Context assembly test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        shutil.rmtree(temp_sessions)


async def main():
    """Run all integration tests."""
    results = []
    
    result1 = await test_session_integration()
    results.append(result1)
    
    result2 = await test_context_prompt_assembly()
    results.append(result2)
    
    print("\n" + "=" * 60)
    print("Integration Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All integration tests passed!")
        return 0
    else:
        print(f"✗ {total - passed} integration test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
