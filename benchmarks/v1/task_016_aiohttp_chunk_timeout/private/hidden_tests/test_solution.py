from solution import ChunkStreamReader

def test_successful_streaming():
    chunks = [(b"a", 0.2), (b"b", 0.3)]
    reader = ChunkStreamReader(chunks)
    assert reader.read_all(time_limit=1.0) == b"ab"
