from solution import upload_artifact_with_retry

call_count = 0
def flaky_upload():
    global call_count
    call_count += 1
    if call_count < 3:
        raise ConnectionError("503 Service Unavailable")
    return True

def test_retry_eventually_succeeds():
    global call_count
    call_count = 0
    assert upload_artifact_with_retry(flaky_upload, max_retries=4) is True
    assert call_count == 3
