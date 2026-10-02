import pytest
from solution import ChunkStreamReader

def test_timeout_raised_before_appending_late_chunk():
    chunks = [(b"chunk1", 0.5), (b"chunk2", 1.0)]
    reader = ChunkStreamReader(chunks)
    with pytest.raises(TimeoutError):
        reader.read_all(time_limit=1.0)
    assert reader.buffer == [b"chunk1"]
