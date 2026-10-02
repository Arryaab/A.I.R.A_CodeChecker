from file_handler import process_file
import os

def test_process_file(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\n")
    # Just testing the happy path
    result = process_file(str(test_file))
    assert result == 0
