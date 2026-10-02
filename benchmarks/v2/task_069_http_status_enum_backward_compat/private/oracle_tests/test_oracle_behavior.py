import pytest
from solution import OK, NOT_FOUND, HTTPStatus

def test_oracle_status_properties():
    assert issubclass(HTTPStatus, int)
    assert OK == 200
    assert hash(OK) == hash(200)
