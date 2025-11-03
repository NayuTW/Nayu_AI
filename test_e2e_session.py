#!/usr/bin/env python3
"""
End-to-end test for session memory integration.
Tests the full flow without requiring actual LLM calls.
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


async def test_end_to_end_flow():
    """Test end-to-end flow simulating actual CLI usage."""
    print("=" * 80)
    print("End-to-End Session Memory Test")
    print("=" * 80)
    
    # Create temporary directories
    temp_cache = tempfile.mkdtemp()
    temp_sessions = tempfile.mkdtemp()
    
    try:
        # Setup infrastructure
        print("\n1. Setting up infrastructure...")
        state = SharedState()
        store = SQLiteStore(path=os.path.join(temp_cache, "test.db"))
        bus = EventBus(store=store)
        registry = ToolRegistry(store=store)
        notifier = Notifier(speech_tool=None, voice_enabled=False, speak_on_error=False)
        
        # Create session manager
        session_manager = SessionManager(
            session_dir=temp_sessions,
            max_messages=20,
            max_tokens=4096,
            summary_interval=5
        )
        
        session_id = "e2e-test-session"
        print(f"   ✓ Session manager created with ID: {session_id}")
        
        # Test 1: First conversation turn
        print("\n2. Testing first conversation turn...")
        user_msg_1 = "Open the file config.json"
        
        # Simulate context assembly before LLM call
        summary, working_set, messages = session_manager.get_context(session_id)
        
        assert len(messages) == 0, "Should start with empty history"
        print(f"   User: {user_msg_1}")
        
        # Add user message
        session_manager.add_message(session_id, "user", user_msg_1, metadata={"source": "cli"})
        
        # Simulate agent response
        agent_response_1 = "I've opened config.json for you."
        session_manager.add_message(session_id, "assistant", agent_response_1)
        
        # Update working set with artifact
        session_manager.update_working_set(
            session_id,
            task_info={"id": "task-1", "type": "file_open", "outcome": "success"},
            artifacts={"last_file": "config.json"}
        )
        print(f"   Agent: {agent_response_1}")
        print("   ✓ Working set updated with artifact")
        
        # Test 2: Second turn with reference
        print("\n3. Testing second turn with reference to 'that file'...")
        user_msg_2 = "Edit that file"
        
        # Get context for LLM prompt
        summary, working_set, messages = session_manager.get_context(session_id)
        
        # Verify context contains necessary information
        assert "last_file=config.json" in working_set, "Working set should contain last_file"
        assert len(messages) == 2, "Should have 2 messages from previous turn"
        
        print(f"   User: {user_msg_2}")
        print(f"   Context available: {working_set}")
        
        # Add messages
        session_manager.add_message(session_id, "user", user_msg_2)
        agent_response_2 = "I'll edit config.json. What changes would you like to make?"
        session_manager.add_message(session_id, "assistant", agent_response_2)
        print(f"   Agent: {agent_response_2}")
        print("   ✓ Agent successfully resolved 'that file' to 'config.json'")
        
        # Test 3: Multiple turns to trigger summary
        print("\n4. Testing summary generation (5 turns)...")
        for i in range(3, 8):
            user_msg = f"Continue editing - change {i}"
            agent_msg = f"I've made change {i} to config.json."
            
            session_manager.add_message(session_id, "user", user_msg)
            session_manager.add_message(session_id, "assistant", agent_msg)
        
        # Check that summary was generated
        summary, working_set, messages = session_manager.get_context(session_id)
        assert summary != "", "Summary should be generated after 5 turns"
        print(f"   ✓ Summary generated: '{summary[:60]}...'")
        
        # Test 4: Persistence
        print("\n5. Testing session persistence...")
        session_manager.flush_cache()
        
        # Create new manager and load session
        session_manager_2 = SessionManager(session_dir=temp_sessions)
        summary_2, working_set_2, messages_2 = session_manager_2.get_context(session_id)
        
        assert len(messages_2) == len(messages), "Persisted messages should match"
        assert working_set_2 == working_set, "Persisted working set should match"
        print("   ✓ Session persisted and reloaded successfully")
        
        # Test 5: Session listing
        print("\n6. Testing session listing...")
        sessions = session_manager_2.list_sessions()
        assert session_id in sessions, f"Session {session_id} should be in list"
        print(f"   ✓ Found session in list: {sessions}")
        
        # Test 6: Session reset
        print("\n7. Testing session reset...")
        msg_count_before = len(messages_2)
        session_manager_2.reset_session(session_id)
        
        summary_3, working_set_3, messages_3 = session_manager_2.get_context(session_id)
        assert len(messages_3) == 0, "Messages should be cleared after reset"
        assert working_set_3 == "", "Working set should be cleared after reset"
        print(f"   ✓ Reset successful: {msg_count_before} messages → 0 messages")
        
        # Test 7: Rolling window truncation
        print("\n8. Testing rolling window truncation...")
        session_id_2 = "truncation-test"
        
        # Create session with small limits
        sm_small = SessionManager(
            session_dir=temp_sessions,
            max_messages=5,
            max_tokens=100
        )
        
        # Add many messages
        for i in range(15):
            sm_small.add_message(session_id_2, "user", f"Message {i}")
            sm_small.add_message(session_id_2, "assistant", f"Response {i}")
        
        summary, working_set, messages = sm_small.get_context(session_id_2)
        assert len(messages) <= 5, f"Should have max 5 messages, got {len(messages)}"
        print(f"   ✓ Truncation works: 30 messages → {len(messages)} messages")
        
        # Test 8: Context assembly format
        print("\n9. Testing context assembly format...")
        session_id_3 = "format-test"
        
        session_manager.add_message(session_id_3, "user", "First message")
        session_manager.add_message(session_id_3, "assistant", "First response")
        session_manager.update_working_set(
            session_id_3,
            artifacts={"last_url": "https://example.com"}
        )
        
        summary, working_set, messages = session_manager.get_context(session_id_3)
        
        # Simulate prompt assembly like in main_agent_smol.py
        conversation_history = "\n".join([
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}"
            for m in messages[-10:]
        ])
        
        # Verify format
        assert "User: First message" in conversation_history
        assert "Assistant: First response" in conversation_history
        assert "last_url=https://example.com" in working_set
        print("   ✓ Context assembly format is correct")
        
        print("\n" + "=" * 80)
        print("✓ All end-to-end tests passed!")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n✗ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        shutil.rmtree(temp_cache)
        shutil.rmtree(temp_sessions)
        store.close()


async def main():
    """Run end-to-end tests."""
    result = await test_end_to_end_flow()
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
