import pytest
from solution import upload_artifact_with_retry

def test_oracle_happy_path_success_after_transient():
    call_count = 0
    def flaky_upload():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("503 Service Unavailable")
        return True
    assert upload_artifact_with_retry(flaky_upload, max_retries=4) is True
    assert call_count == 3

def test_oracle_negative_exhausted_retries():
    def broken_upload():
        raise RuntimeError("Persistent fail")
    with pytest.raises(RuntimeError, match="Upload failed after 3 attempts"):
        upload_artifact_with_retry(broken_upload, max_retries=3)

def test_oracle_boundary_instant_success():
    assert upload_artifact_with_retry(lambda: True, max_retries=1) is True
