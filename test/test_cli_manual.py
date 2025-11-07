#!/usr/bin/env python3
"""
Manual test script to validate CLI session memory behavior.
This script demonstrates how the conversation context is preserved.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.memory.session_manager import SessionManager


def simulate_cli_conversation():
    """Simulate a CLI conversation with session memory."""
    print("=" * 80)
    print("CLI Conversation Simulation - Testing Session Memory")
    print("=" * 80)
    print()
    
    # Initialize session manager
    session_manager = SessionManager(
        session_dir=".nayu_ai/sessions",
        max_messages=20,
        max_tokens=4096,
        summary_interval=5
    )
    
    session_id = "manual-test-session"
    
    # Simulate a multi-turn conversation
    conversations = [
        ("user", "Open the file report.txt"),
        ("assistant", "I've opened report.txt for you."),
        ("user", "What's in that file?"),
        ("assistant", "The file contains a quarterly sales report with three sections: overview, data analysis, and recommendations."),
        ("user", "Can you summarize the recommendations section?"),
        ("assistant", "The recommendations section suggests increasing marketing budget by 15% and focusing on digital channels."),
        ("user", "Add a note about email campaigns to that section"),
        ("assistant", "I've added a note about email campaigns to the recommendations section of report.txt."),
    ]
    
    print("Conversation turns:")
    print("-" * 80)
    
    for i, (role, content) in enumerate(conversations):
        # Add message to session
        session_manager.add_message(session_id, role, content)
        
        # Update working set after first turn
        if i == 1:  # After opening file
            session_manager.update_working_set(
                session_id,
                task_info={"id": f"task-{i}", "type": "file_open", "outcome": "success"},
                artifacts={"last_file": "report.txt"}
            )
        
        # Display conversation
        role_label = "User" if role == "user" else "Agent"
        print(f"\n{role_label}: {content}")
    
    print("\n" + "=" * 80)
    print("Session State After Conversation")
    print("=" * 80)
    
    # Get current state
    summary, working_set, messages = session_manager.get_context(session_id)
    session = session_manager.get_session(session_id)
    
    print(f"\nTotal messages: {len(messages)}")
    print(f"User turns: {session.turn_count}")
    print(f"\nConversation Summary:\n{summary if summary else '(None yet)'}")
    print(f"\nWorking Set:\n{working_set if working_set else '(Empty)'}")
    
    print("\n" + "-" * 80)
    print("Recent Messages (last 5):")
    print("-" * 80)
    for msg in messages[-5:]:
        role_label = "User" if msg.role == "user" else "Agent"
        print(f"{role_label}: {msg.content}")
    
    print("\n" + "=" * 80)
    print("Testing Context Resolution")
    print("=" * 80)
    
    # Simulate next user input that references "that file"
    next_user_msg = "Close that file and open another one"
    print(f"\nUser says: '{next_user_msg}'")
    print("\nContext available to resolve 'that file':")
    print(f"  - Working Set: {working_set}")
    print(f"  - Recent message history shows file operations on report.txt")
    print(f"  - Agent should understand 'that file' refers to 'report.txt'")
    
    print("\n" + "=" * 80)
    print("Testing Session Commands")
    print("=" * 80)
    
    # Test session listing
    print("\n1. Listing sessions:")
    sessions = session_manager.list_sessions()
    print(f"   Found {len(sessions)} session(s):")
    for s in sessions:
        print(f"     - {s}")
    
    # Test session persistence
    print("\n2. Testing persistence (flush and reload):")
    session_manager.flush_cache()
    
    # Create new manager
    session_manager2 = SessionManager(session_dir=".nayu_ai/sessions")
    summary2, working_set2, messages2 = session_manager2.get_context(session_id)
    
    if len(messages2) == len(messages):
        print("   ✓ Session persisted correctly")
    else:
        print(f"   ✗ Persistence issue: {len(messages)} vs {len(messages2)} messages")
    
    # Test session reset
    print("\n3. Testing session reset:")
    print(f"   Before reset: {len(messages2)} messages")
    # Don't actually reset so user can see the session in manual testing
    # session_manager2.reset_session(session_id)
    # summary3, working_set3, messages3 = session_manager2.get_context(session_id)
    # print(f"   After reset: {len(messages3)} messages")
    print("   (Skipping actual reset to preserve session for manual testing)")
    
    print("\n" + "=" * 80)
    print("✓ CLI Conversation Simulation Complete")
    print("=" * 80)
    print(f"\nSession '{session_id}' has been created in .nayu_ai/sessions/")
    print("You can now run the actual CLI and test with this session.")
    print()


if __name__ == "__main__":
    simulate_cli_conversation()
