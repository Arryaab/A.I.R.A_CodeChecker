import pytest
from solution import assemble_stream_chunks

def test_oracle_empty_and_single():
    assert assemble_stream_chunks([]) == ""
    assert assemble_stream_chunks(["only"]) == "only"
