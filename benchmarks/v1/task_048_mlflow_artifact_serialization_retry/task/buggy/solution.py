def upload_artifact_with_retry(upload_fn, max_retries: int = 3) -> bool:
    # BUG: fails immediately on first exception without retrying
    try:
        return upload_fn()
    except Exception:
        raise RuntimeError("Upload failed")
