import pytest
from solution import compare_semver

def test_distinct_major_versions():
    assert compare_semver("2.0.0", "1.0.0") == 1
    assert compare_semver("1.0.0", "2.0.0") == -1

def test_identical_versions():
    assert compare_semver("1.2.3", "1.2.3") == 0
