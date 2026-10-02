from typing import List

def pack_binary_frames(frames: List[bytes]) -> bytes:
    """Packs binary frames into contiguous payload."""
    # BUG: byte-by-byte accumulation repeatedly re-allocates immutable bytes object
    output = b""
    for frame in frames:
        output = output + frame
    return output
