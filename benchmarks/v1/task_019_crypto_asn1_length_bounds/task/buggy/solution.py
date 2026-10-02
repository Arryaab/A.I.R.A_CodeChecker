def parse_asn1_length(data: bytes, offset: int = 0) -> tuple[int, int]:
    # Returns (length, new_offset)
    first = data[offset]
    if first < 0x80:
        return first, offset + 1
    # Long form
    num_octets = first & 0x7F
    # BUG: does not check if offset + 1 + num_octets exceeds len(data)
    length = int.from_bytes(data[offset + 1:offset + 1 + num_octets], "big")
    return length, offset + 1 + num_octets
