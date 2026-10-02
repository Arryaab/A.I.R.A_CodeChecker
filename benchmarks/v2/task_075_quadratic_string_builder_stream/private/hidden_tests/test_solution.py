import pytest
import time
from solution import assemble_stream_chunks

def test_linear_scaling_large_stream():
    # 25,000 small chunks
    chunks = ["chunk_data_"] * 25000
    t0 = time.time()
    res = assemble_stream_chunks(chunks)
    elapsed = time.time() - t0
    assert len(res) == 25000 * 11
    # Linear join takes < 0.05s, while quadratic concatenation takes > 0.8s
    assert elapsed < 0.20, f"Quadratic latency bottleneck: took {elapsed:.2f}s"
