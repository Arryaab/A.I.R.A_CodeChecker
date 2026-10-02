import pytest
from solution import compare_semver

def test_oracle_semver_lifecycle():
    versions = ["1.0.0-alpha", "1.0.0-beta", "1.0.0-rc", "1.0.0"]
    for i in range(len(versions) - 1):
        assert compare_semver(versions[i], versions[i+1]) == -1
        assert compare_semver(versions[i+1], versions[i]) == 1
