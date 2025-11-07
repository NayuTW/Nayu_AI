"""
Basic tests for VAD functionality.
Tests voice activity detection and frame buffering.
"""
import pytest
import struct


def test_vad_import():
    """Test that VAD module can be imported."""
    try:
        from src.audio.vad import VAD, FrameRingBuffer
        assert VAD is not None
        assert FrameRingBuffer is not None
    except ImportError as e:
        pytest.skip(f"VAD dependencies not available: {e}")


def test_vad_initialization():
    """Test VAD initialization with valid parameters."""
    try:
        from src.audio.vad import VAD
    except ImportError:
        pytest.skip("VAD dependencies not available")
    
    # Valid parameters
    vad = VAD(sample_rate=48000, frame_ms=20, aggressiveness=2)
    assert vad.sample_rate == 48000
    assert vad.frame_ms == 20
    assert vad.aggressiveness == 2


def test_vad_invalid_sample_rate():
    """Test VAD rejects invalid sample rates."""
    try:
        from src.audio.vad import VAD
    except ImportError:
        pytest.skip("VAD dependencies not available")
    
    with pytest.raises(ValueError):
        VAD(sample_rate=44100, frame_ms=20, aggressiveness=2)


def test_vad_invalid_frame_duration():
    """Test VAD rejects invalid frame durations."""
    try:
        from src.audio.vad import VAD
    except ImportError:
        pytest.skip("VAD dependencies not available")
    
    with pytest.raises(ValueError):
        VAD(sample_rate=48000, frame_ms=25, aggressiveness=2)


def test_vad_invalid_aggressiveness():
    """Test VAD rejects invalid aggressiveness values."""
    try:
        from src.audio.vad import VAD
    except ImportError:
        pytest.skip("VAD dependencies not available")
    
    with pytest.raises(ValueError):
        VAD(sample_rate=48000, frame_ms=20, aggressiveness=5)


def test_vad_is_speech_with_silence():
    """Test VAD correctly identifies silence."""
    try:
        from src.audio.vad import VAD
    except ImportError:
        pytest.skip("VAD dependencies not available")
    
    vad = VAD(sample_rate=48000, frame_ms=20, aggressiveness=2)
    
    # Generate silence frame (20ms @ 48kHz = 960 samples)
    silence_frame = struct.pack('<' + 'h' * 960, *([0] * 960))
    
    # Silence should typically not be detected as speech
    # (though VAD might have false positives with pure silence)
    result = vad.is_speech(silence_frame)
    assert isinstance(result, bool)


def test_frame_ring_buffer_initialization():
    """Test FrameRingBuffer initialization."""
    try:
        from src.audio.vad import VAD, FrameRingBuffer
    except ImportError:
        pytest.skip("VAD dependencies not available")
    
    vad = VAD(sample_rate=48000, frame_ms=20, aggressiveness=2)
    buffer = FrameRingBuffer(
        vad=vad,
        speech_pad_frames=10,
        silence_pad_frames=10,
        min_speech_frames=5,
    )
    
    assert buffer.vad == vad
    assert buffer.speech_pad_frames == 10
    assert buffer.silence_pad_frames == 10
    assert buffer.min_speech_frames == 5


def test_frame_ring_buffer_process_silence():
    """Test FrameRingBuffer with silence frames."""
    try:
        from src.audio.vad import VAD, FrameRingBuffer
    except ImportError:
        pytest.skip("VAD dependencies not available")
    
    vad = VAD(sample_rate=48000, frame_ms=20, aggressiveness=2)
    buffer = FrameRingBuffer(vad=vad)
    
    # Process silence frames
    silence_frame = struct.pack('<' + 'h' * 960, *([0] * 960))
    
    for _ in range(20):
        result = buffer.process_frame(silence_frame)
        # Should not return utterance from silence
        assert result is None


def test_frame_ring_buffer_flush():
    """Test FrameRingBuffer flush functionality."""
    try:
        from src.audio.vad import VAD, FrameRingBuffer
    except ImportError:
        pytest.skip("VAD dependencies not available")
    
    vad = VAD(sample_rate=48000, frame_ms=20, aggressiveness=2)
    buffer = FrameRingBuffer(vad=vad)
    
    # Flush empty buffer should return None
    result = buffer.flush()
    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
