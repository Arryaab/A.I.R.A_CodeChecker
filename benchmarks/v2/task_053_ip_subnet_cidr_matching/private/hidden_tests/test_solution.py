import pytest
from solution import is_ip_in_cidr

def test_unnormalized_network_address():
    # If CIDR is given as 192.168.1.55/24, it should still match 192.168.1.1
    assert is_ip_in_cidr("192.168.1.1", "192.168.1.55/24") is True

def test_prefix_32_host_route():
    assert is_ip_in_cidr("10.1.2.3", "10.1.2.3/32") is True
    assert is_ip_in_cidr("10.1.2.4", "10.1.2.3/32") is False

def test_prefix_0_all_routes():
    assert is_ip_in_cidr("1.2.3.4", "0.0.0.0/0") is True
