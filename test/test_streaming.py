#!/usr/bin/env python3
"""
Test script for streaming response functionality.
"""
import sys
import os
import asyncio
import tempfile
import shutil

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.core.events import EventBus
from src.agents.core.streaming_handler import StreamingResponseHandler, StreamChunk
from src.agents.core.store import SQLiteStore


async def test_stream_chunk():
    """Test StreamChunk dataclass."""
    print("\n1. Testing StreamChunk...")
    
    try:
        chunk = StreamChunk(content="Hello", is_final=False)
        assert chunk.content == "Hello"
        assert not chunk.is_final
        assert chunk.timestamp > 0
        
        chunk2 = StreamChunk(content="World", is_final=True, metadata={"test": "value"})
        assert chunk2.is_final
        assert chunk2.metadata["test"] == "value"
        
        print("   ✓ StreamChunk works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_streaming_handler_basic():
    """Test basic streaming handler functionality."""
    print("\n2. Testing StreamingResponseHandler basic functionality...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        store = SQLiteStore(path=os.path.join(temp_dir, "test.db"))
        bus = EventBus(store=store)
        handler = StreamingResponseHandler(bus=bus, buffer_size=2)
        
        # Create a simple async generator
        async def token_generator():
            tokens = ["Hello", " ", "world", "!"]
            for token in tokens:
                yield token
                await asyncio.sleep(0.01)
        
        # Collect events
        events = []
        event_queue = await bus.subscribe()
        
        async def collect_events():
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=2.0)
                    events.append(event)
                except asyncio.TimeoutError:
                    break
        
        # Run streaming and event collection concurrently
        collect_task = asyncio.create_task(collect_events())
        
        result = await handler.stream_response(
            generator=token_generator(),
            source="test",
            session_id="test-session"
        )
        
        await asyncio.sleep(0.5)  # Let events finish
        collect_task.cancel()
        
        # Verify result
        assert result == "Hello world!", f"Expected 'Hello world!', got '{result}'"
        
        # Verify events were emitted
        chunk_events = [e for e in events if e.type == "stream.chunk"]
        complete_events = [e for e in events if e.type == "stream.complete"]
        
        assert len(chunk_events) > 0, "Should have chunk events"
        assert len(complete_events) == 1, "Should have one complete event"
        
        store.close()
        print("   ✓ StreamingResponseHandler basic functionality works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


async def test_streaming_interrupt():
    """Test streaming with interrupt."""
    print("\n3. Testing streaming with interrupt...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        store = SQLiteStore(path=os.path.join(temp_dir, "test.db"))
        bus = EventBus(store=store)
        handler = StreamingResponseHandler(bus=bus, buffer_size=1, check_interrupt_every=2)
        
        # Create a generator with many tokens
        async def long_generator():
            for i in range(20):
                yield f"token{i} "
                await asyncio.sleep(0.01)
        
        # Signal interrupt after a short delay
        async def signal_interrupt():
            await asyncio.sleep(0.05)
            await bus.signal_interrupt("user.input", {"text": "interrupt"})
        
        # Start interrupt signal task
        interrupt_task = asyncio.create_task(signal_interrupt())
        
        # Run streaming
        result = await handler.stream_response(
            generator=long_generator(),
            source="test",
            session_id="test-session"
        )
        
        await interrupt_task
        
        # Verify that handler detected interrupt
        assert handler.was_interrupted(), "Should have been interrupted"
        
        # Result should be partial (not all 20 tokens)
        assert len(result) < 200, f"Result should be partial, got length {len(result)}"
        
        store.close()
        print("   ✓ Streaming with interrupt works")
        return True
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


async def test_streaming_buffer():
    """Test streaming buffer management."""
    print("\n4. Testing streaming buffer management...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        store = SQLiteStore(path=os.path.join(temp_dir, "test.db"))
        bus = EventBus(store=store)
        
        # Test with different buffer sizes
        for buffer_size in [1, 3, 5]:
            handler = StreamingResponseHandler(bus=bus, buffer_size=buffer_size)
            
            async def token_generator():
                for i in range(10):
                    yield f"{i}"
            
            result = await handler.stream_response(
                generator=token_generator(),
                source="test",
                session_id="test-session"
            )
            
            assert result == "0123456789", f"Expected full result, got '{result}'"
        
        store.close()
        print("   ✓ Streaming buffer management works")
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
    print("Testing Streaming Response Functionality")
    print("=" * 60)
    
    tests = [
        test_stream_chunk,
        test_streaming_handler_basic,
        test_streaming_interrupt,
        test_streaming_buffer,
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
