def decode_header(raw_bytes: bytes) -> str:
    # BUG: Crashes on non-utf8 headers without fallback
    return raw_bytes.decode('utf-8')
