import pytest
from solution import resolve_safe_extract_path

def test_oracle_traversal_variations():
    cases = ["../evil.sh", "..\\evil.bat", "/etc/shadow", "foo/bar/../../../../secret"]
    for c in cases:
        try:
            res = resolve_safe_extract_path("/tmp/safe", c)
            # If it didn't raise, ensure it did not escape
            import os
            assert res.startswith(os.path.abspath("/tmp/safe") + os.sep)
        except ValueError:
            pass
