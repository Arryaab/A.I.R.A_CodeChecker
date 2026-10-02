from solution import validate_query_param

def test_regex_pattern_enforcement():
    assert validate_query_param("user_123", pattern=r"^[a-z]+_\d+$") is True
    assert validate_query_param("User_123", pattern=r"^[a-z]+_\d+$") is False
