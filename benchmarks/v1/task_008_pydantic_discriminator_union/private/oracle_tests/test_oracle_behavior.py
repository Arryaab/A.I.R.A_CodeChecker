import pytest
from solution import parse_event

def test_oracle_happy_path_click_event():
    res = parse_event({"type": "click", "x": 10, "y": 20})
    assert res == {"kind": "click", "x": 10, "y": 20}

def test_oracle_happy_path_hover_event():
    res = parse_event({"type": "hover", "duration": 5.5})
    assert res == {"kind": "hover", "duration": 5.5}

def test_oracle_negative_missing_type_raises():
    with pytest.raises(ValueError, match="Missing discriminator 'type'"):
        parse_event({"x": 10})

def test_oracle_negative_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown event type"):
        parse_event({"type": "scroll"})

def test_oracle_negative_non_dict_raises():
    with pytest.raises(ValueError):
        parse_event("not_a_dict")
