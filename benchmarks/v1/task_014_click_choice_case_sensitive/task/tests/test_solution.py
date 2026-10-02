from solution import match_choice

def test_case_insensitive_matching():
    choices = ["Fast", "Standard", "Deep"]
    assert match_choice("fast", choices, case_sensitive=False) == "Fast"
