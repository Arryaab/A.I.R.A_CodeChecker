import pytest
from solution import assemble_stream_chunks

def test_basic_assembly():
    chunks = ["Hello", " ", "World", "!"]
    assert assemble_stream_chunks(chunks) == "Hello World!"
