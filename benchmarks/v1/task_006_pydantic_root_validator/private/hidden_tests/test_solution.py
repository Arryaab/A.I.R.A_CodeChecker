from solution import validate_user_payload

def test_root_validator_no_name_fields():
    data = {"role": "guest"}
    assert validate_user_payload(data) == {"role": "guest"}
