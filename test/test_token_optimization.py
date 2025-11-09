#!/usr/bin/env python3
"""
Test script for token optimization functionality.
"""
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.memory.session_manager import SessionManager


def test_aggressive_trimming():
    """Test aggressive context trimming."""
    print("\n1. Testing aggressive trimming...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create manager with aggressive trimming
        manager = SessionManager(
            session_dir=temp_dir,
            max_messages=10,
            max_tokens=500,
            aggressive_trim=True
        )
        
        # Add many messages
        for i in range(20):
            manager.add_message("test-session", "user", f"Message {i}")
            manager.add_message("test-session", "assistant", f"Response {i}")
        
        # Check that messages were aggressively trimmed
        session = manager.get_session("test-session")
        assert len(session.messages) <= 10, f"Expected <= 10 messages, got {len(session.messages)}"
        
        # Verify most recent messages are kept
        last_msg = session.messages[-1]
        assert "Response 19" in last_msg.content, "Most recent message should be preserved"
        
        print("   ✓ Aggressive trimming works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_compact_context():
    """Test compact context retrieval."""
    print("\n2. Testing compact context...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = SessionManager(session_dir=temp_dir)
        
        # Add messages
        for i in range(15):
            manager.add_message("test-session", "user", f"User message {i}")
            manager.add_message("test-session", "assistant", f"Assistant response {i}")
        
        # Get compact context (max 5 messages)
        summary, working_set, messages = manager.get_compact_context("test-session", max_messages=5)
        
        assert len(messages) == 5, f"Expected 5 messages, got {len(messages)}"
        
        # Verify we got the most recent messages
        assert "User message 13" in messages[-2].content or "Assistant response 14" in messages[-1].content
        
        print("   ✓ Compact context works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_token_estimation():
    """Test token estimation."""
    print("\n3. Testing token estimation...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = SessionManager(session_dir=temp_dir)
        
        # Add messages with known content
        manager.add_message("test-session", "user", "Hello world")  # ~3 tokens
        manager.add_message("test-session", "assistant", "Hi there")  # ~3 tokens
        
        # Estimate tokens
        estimated = manager.estimate_context_tokens("test-session")
        
        # Should be roughly 6 tokens (very rough estimate)
        assert estimated > 0, "Should have positive token estimate"
        assert estimated < 50, "Estimate should be reasonable for short messages"
        
        print(f"   ✓ Token estimation works (estimated: {estimated} tokens)")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_default_compact_context():
    """Test compact context with default parameters."""
    print("\n4. Testing default compact context (5 messages)...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        manager = SessionManager(session_dir=temp_dir)
        
        # Add 20 messages
        for i in range(20):
            manager.add_message("test-session", "user", f"Message {i}")
        
        # Get compact context with default (5 messages)
        summary, working_set, messages = manager.get_compact_context("test-session")
        
        assert len(messages) == 5, f"Expected 5 messages by default, got {len(messages)}"
        
        # Check we got the last 5
        assert "Message 19" in messages[-1].content
        assert "Message 15" in messages[0].content
        
        print("   ✓ Default compact context works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_token_budget_enforcement():
    """Test that token budget is enforced."""
    print("\n5. Testing token budget enforcement...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create manager with very small token budget
        manager = SessionManager(
            session_dir=temp_dir,
            max_messages=20,
            max_tokens=100,  # Very small
            aggressive_trim=True
        )
        
        # Add messages with substantial content
        long_content = "This is a long message " * 10  # ~200+ characters
        for i in range(10):
            manager.add_message("test-session", "user", long_content)
        
        # Check that token budget was enforced
        session = manager.get_session("test-session")
        estimated_tokens = manager.estimate_context_tokens("test-session")
        
        # Should be reasonably close to budget (may slightly exceed due to minimum 3 messages)
        # With 3 minimum messages of ~200 chars each, we expect ~150 tokens
        assert estimated_tokens < 500, f"Token budget not enforced: {estimated_tokens} tokens"
        assert len(session.messages) >= 3, "Should keep at least 3 messages"
        
        print(f"   ✓ Token budget enforcement works ({estimated_tokens} tokens, {len(session.messages)} messages)")
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
    print("Testing Token Optimization")
    print("=" * 60)
    
    tests = [
        test_aggressive_trimming,
        test_compact_context,
        test_token_estimation,
        test_default_compact_context,
        test_token_budget_enforcement,
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
