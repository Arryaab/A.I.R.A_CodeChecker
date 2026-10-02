from solution import validate_query_param

def test_exact_max_length_boundary():
    val = "a" * 50
    assert validate_query_param(val, max_length=50) is True
