from solution import is_domain_match

def test_subdomain_collision_prevention():
    assert is_domain_match("notexample.com", "example.com") is False
    assert is_domain_match("api.example.com", "example.com") is True
