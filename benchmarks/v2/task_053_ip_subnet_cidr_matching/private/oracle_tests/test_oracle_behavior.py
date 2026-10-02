import pytest
from solution import is_ip_in_cidr

def test_oracle_cidr_edge_cases():
    assert is_ip_in_cidr("192.168.1.255", "192.168.1.0/24") is True
    assert is_ip_in_cidr("192.168.1.0", "192.168.1.0/24") is True
    assert is_ip_in_cidr("192.168.2.0", "192.168.1.0/24") is False
