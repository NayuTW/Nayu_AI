#!/usr/bin/env python3
"""
Simple tests to validate performance improvements.
Tests the optimized components without requiring full system setup.
"""
import os
import sys
import time
import tempfile
import shutil

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_store_performance():
    """Test SQLite store optimizations."""
    print("Testing SQLite store performance...")
    from src.agents.core.store import SQLiteStore
    
    # Create temp db
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        store = SQLiteStore(path=db_path)
        
        # Test batch event insertion
        start = time.time()
        for i in range(100):
            store.append_event(f"test.event", {"index": i, "data": f"test_{i}"})
        store.flush()  # Force flush
        elapsed = time.time() - start
        print(f"  ✓ Inserted 100 events in {elapsed:.3f}s")
        
        # Test event retrieval
        start = time.time()
        events = store.get_recent_events(limit=50)
        elapsed = time.time() - start
        print(f"  ✓ Retrieved {len(events)} events in {elapsed:.3f}s")
        
        # Test cleanup
        store.close()
        print("  ✓ Store closed successfully")
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
        # Clean up WAL files
        for ext in ['-wal', '-shm']:
            wal_file = db_path + ext
            if os.path.exists(wal_file):
                os.unlink(wal_file)


def test_embedder_lazy_loading():
    """Test lazy loading of embedding models."""
    print("\nTesting embedder lazy loading...")
    try:
        from src.agents.embeddings.local_embedder import LocalEmbedder
        
        # Test lazy initialization
        start = time.time()
        embedder = LocalEmbedder(lazy_load=True)
        init_time = time.time() - start
        print(f"  ✓ Lazy init took {init_time:.3f}s (should be < 0.1s)")
        assert init_time < 0.1, "Lazy init should be instant"
        
        # Test actual embedding (this will trigger model load)
        start = time.time()
        vec1 = embedder.embed_text("test query")
        first_embed_time = time.time() - start
        print(f"  ✓ First embedding took {first_embed_time:.3f}s (includes model load)")
        
        # Test caching
        start = time.time()
        vec2 = embedder.embed_text("test query")
        cached_time = time.time() - start
        print(f"  ✓ Cached embedding took {cached_time:.3f}s (should be < 0.1s)")
        assert cached_time < first_embed_time * 0.5, "Cached query should be much faster"
        
        # Verify results are the same
        assert len(vec1) == len(vec2), "Vectors should have same length"
        assert vec1 == vec2, "Cached result should match original"
        print("  ✓ Caching working correctly")
    except ImportError as e:
        print(f"  ⚠ Skipping: Missing dependencies ({e})")


def test_event_bus():
    """Test event bus optimizations."""
    print("\nTesting event bus...")
    import asyncio
    from src.agents.core.events import EventBus
    
    async def run_test():
        bus = EventBus()
        
        # Subscribe multiple listeners
        queues = [await bus.subscribe() for _ in range(5)]
        
        # Publish events
        start = time.time()
        for i in range(50):
            await bus.publish(f"test.event.{i % 5}", {"index": i})
        elapsed = time.time() - start
        print(f"  ✓ Published 50 events to 5 subscribers in {elapsed:.3f}s")
        
        # Verify events received
        for q in queues:
            count = q.qsize()
            assert count == 50, f"Expected 50 events, got {count}"
        print("  ✓ All subscribers received all events")
        
        # Cleanup
        for q in queues:
            await bus.unsubscribe(q)
    
    asyncio.run(run_test())


def test_requests_session_pooling():
    """Test HTTP session pooling."""
    print("\nTesting HTTP session pooling...")
    try:
        from src.agents.tools.webbrowser import _get_requests_session
        
        # Get session twice - should return the same instance
        session1 = _get_requests_session()
        session2 = _get_requests_session()
        
        assert session1 is session2, "Should return same session instance"
        print("  ✓ Session pooling working correctly")
        
        # Verify session has proper headers
        assert "User-Agent" in session1.headers
        print("  ✓ Session configured with proper headers")
    except ImportError as e:
        print(f"  ⚠ Skipping: Missing dependencies ({e})")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Performance Optimization Validation Tests")
    print("=" * 60)
    
    try:
        test_store_performance()
        test_embedder_lazy_loading()
        test_event_bus()
        test_requests_session_pooling()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
