import pytest
from solution import quote_identifier

def test_embedded_quotes_escaped():
    assert quote_identifier('user"name') == '"user""name"'
    assert quote_identifier('evil"; DROP TABLE users; --') == '"evil""; DROP TABLE users; --"'

def test_null_byte_rejected():
    with pytest.raises(ValueError):
        quote_identifier("users\x00evil")
