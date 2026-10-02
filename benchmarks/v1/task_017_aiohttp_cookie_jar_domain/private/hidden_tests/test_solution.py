from solution import is_domain_match

def test_exact_domain_match():
    assert is_domain_match("example.com", "example.com") is True
    assert is_domain_match("example.com", ".example.com") is True
