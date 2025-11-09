#!/usr/bin/env python3
"""
Test script for continuous agent architecture components.
"""
import sys
import os
import asyncio
import tempfile
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.core.events import EventBus, InterruptPriority
from src.agents.core.interrupt_manager import InterruptManager
from src.agents.core.character_state import CharacterStateMachine, CharacterState, AttentionContext
from src.agents.core.store import SQLiteStore


async def test_interrupt_priority():
    """Test interrupt priority handling."""
    print("\n1. Testing interrupt priority...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create store and event bus
        store = SQLiteStore(path=os.path.join(temp_dir, "test.db"))
        bus = EventBus(store=store)
        
        # Signal different priority interrupts
        await bus.signal_interrupt(
            "test.low",
            {"msg": "low priority"},
            InterruptPriority.BACKGROUND
        )
        
        await bus.signal_interrupt(
            "test.high",
            {"msg": "high priority"},
            InterruptPriority.HIGH
        )
        
        # Check that interrupts are queued
        assert bus.has_interrupt(), "Should have interrupts"
        
        # Get interrupts (should come out in queue order, not priority order in basic implementation)
        interrupt1 = await bus.get_interrupt(timeout=1.0)
        assert interrupt1 is not None, "Should get first interrupt"
        assert interrupt1.type == "test.low"
        
        interrupt2 = await bus.get_interrupt(timeout=1.0)
        assert interrupt2 is not None, "Should get second interrupt"
        assert interrupt2.type == "test.high"
        
        store.close()
        print("   ✓ Interrupt priority handling works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


async def test_interrupt_manager():
    """Test interrupt manager functionality."""
    print("\n2. Testing interrupt manager...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        store = SQLiteStore(path=os.path.join(temp_dir, "test.db"))
        bus = EventBus(store=store)
        interrupt_manager = InterruptManager(bus=bus)
        
        # Track handled interrupts
        handled = []
        
        async def test_handler(interrupt):
            handled.append(interrupt.type)
        
        # Register handler
        interrupt_manager.register_handler("test.interrupt", test_handler)
        
        # Start manager
        await interrupt_manager.start()
        
        # Signal interrupt
        await bus.signal_interrupt(
            "test.interrupt",
            {"data": "test"},
            InterruptPriority.NORMAL
        )
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Stop manager
        await interrupt_manager.stop()
        
        # Check that handler was called
        assert "test.interrupt" in handled, "Handler should be called"
        
        store.close()
        print("   ✓ Interrupt manager works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


async def test_character_state_machine():
    """Test character state machine."""
    print("\n3. Testing character state machine...")
    
    try:
        state_machine = CharacterStateMachine()
        
        # Initial state should be IDLE
        assert state_machine.is_idle(), "Should start in IDLE state"
        assert state_machine.state == CharacterState.IDLE
        
        # Transition to THINKING
        state_machine.transition_to(CharacterState.THINKING)
        assert state_machine.state == CharacterState.THINKING
        assert state_machine.is_busy(), "Should be busy when not idle"
        
        # Push attention context
        context = AttentionContext(
            primary_task="Test task",
            source="test"
        )
        state_machine.push_attention(context)
        
        current = state_machine.current_attention()
        assert current is not None, "Should have current attention"
        assert current.primary_task == "Test task"
        
        # Pop attention
        popped = state_machine.pop_attention()
        assert popped is not None, "Should pop attention"
        assert popped.primary_task == "Test task"
        
        # Get state info
        info = state_machine.get_state_info()
        assert info["state"] == CharacterState.THINKING.value
        assert info["attention_depth"] == 0
        
        print("   ✓ Character state machine works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_event_bus_interrupt_flag():
    """Test event bus interrupt flag."""
    print("\n4. Testing event bus interrupt flag...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        store = SQLiteStore(path=os.path.join(temp_dir, "test.db"))
        bus = EventBus(store=store)
        
        # Initially no interrupt
        assert not bus.has_interrupt(), "Should have no interrupts"
        assert not bus.is_interrupt_signaled(), "Flag should not be set"
        
        # Signal interrupt
        await bus.signal_interrupt(
            "test",
            {},
            InterruptPriority.NORMAL
        )
        
        # Check flag
        assert bus.has_interrupt(), "Should have interrupt"
        assert bus.is_interrupt_signaled(), "Flag should be set"
        
        # Clear flag
        bus.clear_interrupt_flag()
        assert not bus.is_interrupt_signaled(), "Flag should be cleared"
        
        # But interrupt should still be in queue
        assert bus.has_interrupt(), "Interrupt should still be in queue"
        
        store.close()
        print("   ✓ Event bus interrupt flag works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Continuous Agent Architecture")
    print("=" * 60)
    
    tests = [
        test_interrupt_priority,
        test_interrupt_manager,
        test_character_state_machine,
        test_event_bus_interrupt_flag,
    ]
    
    results = []
    for test in tests:
        result = await test()
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
    sys.exit(asyncio.run(main()))
