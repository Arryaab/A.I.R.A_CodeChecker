import pytest
from solution import is_ip_in_cidr

def test_basic_inclusion():
    assert is_ip_in_cidr("192.168.1.50", "192.168.1.0/24") is True

def test_basic_exclusion():
    assert is_ip_in_cidr("10.0.0.1", "192.168.1.0/24") is False
