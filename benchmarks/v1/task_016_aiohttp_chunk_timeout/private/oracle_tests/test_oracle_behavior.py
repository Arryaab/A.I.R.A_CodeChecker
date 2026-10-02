import pytest
from solution import ChunkStreamReader

def test_oracle_happy_path_all_chunks():
    chunks = [(b"alpha", 0.1), (b"beta", 0.2)]
    reader = ChunkStreamReader(chunks)
    assert reader.read_all(time_limit=1.0) == b"alphabeta"

def test_oracle_negative_timeout_excludes_late_chunk():
    chunks = [(b"ok1", 0.3), (b"late_chunk", 1.0)]
    reader = ChunkStreamReader(chunks)
    with pytest.raises(TimeoutError, match="Read timeout exceeded"):
        reader.read_all(time_limit=0.5)
    assert reader.buffer == [b"ok1"]

def test_oracle_regression_first_chunk_timeout():
    chunks = [(b"too_late", 2.0)]
    reader = ChunkStreamReader(chunks)
    with pytest.raises(TimeoutError):
        reader.read_all(time_limit=1.0)
    assert reader.buffer == []
