import pytest
from solution import upload_artifact_with_retry

def always_failing_upload():
    raise ConnectionResetError("Connection refused")

def test_exceeded_retries_raises():
    with pytest.raises(RuntimeError):
        upload_artifact_with_retry(always_failing_upload, max_retries=2)
