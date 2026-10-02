import base64
import json
import pytest
from solution import decode_cursor

def test_opaque_b64_cursor():
    token = base64.b64encode(json.dumps({"offset": 25}).encode()).decode()
    assert decode_cursor(token) == 25
