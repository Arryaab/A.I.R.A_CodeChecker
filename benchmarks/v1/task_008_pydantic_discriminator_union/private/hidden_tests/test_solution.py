import pytest
from solution import parse_event

def test_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown event type"):
        parse_event({"type": "scroll", "offset": 50})
