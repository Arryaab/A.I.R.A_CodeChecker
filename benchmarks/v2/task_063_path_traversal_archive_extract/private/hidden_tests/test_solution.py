import pytest
from solution import resolve_safe_extract_path

def test_relative_escape_raises():
    with pytest.raises(ValueError):
        resolve_safe_extract_path("/tmp/extract", "../../../etc/passwd")

def test_nested_parent_traversal():
    with pytest.raises(ValueError):
        resolve_safe_extract_path("/tmp/extract", "sub/../../escape.txt")
