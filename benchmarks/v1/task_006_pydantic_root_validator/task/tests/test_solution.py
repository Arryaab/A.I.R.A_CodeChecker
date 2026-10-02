from solution import validate_user_payload

def test_root_validator_keeps_original_fields():
    data = {"first_name": "Alan", "last_name": "Turing", "role": "researcher"}
    res = validate_user_payload(data)
    assert res["full_name"] == "Alan Turing"
    assert res["role"] == "researcher"
