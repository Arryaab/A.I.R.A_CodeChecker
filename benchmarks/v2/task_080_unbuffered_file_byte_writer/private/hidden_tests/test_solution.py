import pytest
import time
from solution import pack_binary_frames

def test_large_frame_throughput():
    frames = [b"FRAME_HEADER_PAYLOAD_CHUNK_" for _ in range(30000)]
    t0 = time.time()
    packed = pack_binary_frames(frames)
    elapsed = time.time() - t0
    assert len(packed) == 30000 * 27
    # Join takes < 0.05s, repeated concatenation takes > 0.9s
    assert elapsed < 0.20, f"Unbuffered byte allocation latency: took {elapsed:.2f}s"
