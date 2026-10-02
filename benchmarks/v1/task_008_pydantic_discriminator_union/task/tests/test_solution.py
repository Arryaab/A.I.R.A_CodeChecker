import pytest
from solution import parse_event

def test_parse_click_event():
    res = parse_event({"type": "click", "x": 100, "y": 200})
    assert res == {"kind": "click", "x": 100, "y": 200}

def test_missing_type_raises():
    with pytest.raises(ValueError):
        parse_event({"x": 100})
