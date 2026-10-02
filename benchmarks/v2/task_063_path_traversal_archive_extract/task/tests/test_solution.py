import os
import pytest
from solution import resolve_safe_extract_path

def test_safe_relative_path():
    path = resolve_safe_extract_path("/tmp/extract", "docs/readme.txt")
    assert path.endswith("docs" + os.sep + "readme.txt")
