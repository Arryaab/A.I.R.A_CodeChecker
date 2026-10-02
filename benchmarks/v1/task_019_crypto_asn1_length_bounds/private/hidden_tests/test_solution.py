from solution import parse_asn1_length

def test_asn1_short_and_long_form():
    short = bytes([0x45])
    assert parse_asn1_length(short, 0) == (0x45, 1)
    long_hdr = bytes([0x82, 0x01, 0x00])
    assert parse_asn1_length(long_hdr, 0) == (256, 3)
