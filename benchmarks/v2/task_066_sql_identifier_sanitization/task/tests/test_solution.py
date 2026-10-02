import pytest
from solution import quote_identifier

def test_standard_identifier():
    assert quote_identifier("users") == '"users"'
    assert quote_identifier("first_name") == '"first_name"'
