def pkcs7_unpad(data: bytes, block_size: int = 16) -> bytes:
    if not data or len(data) % block_size != 0:
        raise ValueError("Invalid block length")
    pad_len = data[-1]
    # BUG: fails to verify that ALL pad_len bytes actually match pad_len
    return data[:-pad_len]
