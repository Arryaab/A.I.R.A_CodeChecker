import pytest
from solution import compare_semver

def test_normal_versus_prerelease():
    # 1.0.0 is greater than 1.0.0-alpha
    assert compare_semver("1.0.0", "1.0.0-alpha") == 1
    assert compare_semver("1.0.0-alpha", "1.0.0") == -1

def test_prerelease_ordering():
    assert compare_semver("1.0.0-beta", "1.0.0-alpha") == 1
    assert compare_semver("1.0.0-alpha.1", "1.0.0-alpha.2") == -1
