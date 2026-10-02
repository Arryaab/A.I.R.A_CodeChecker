import pytest
from solution import execute_middleware_chain, CustomHTTPException

def test_oracle_happy_path_normal_handler():
    res = execute_middleware_chain(lambda req: {"status": 200, "data": "ok"}, {})
    assert res == {"status": 200, "data": "ok"}

def test_oracle_negative_custom_http_exception():
    def failing_handler(req):
        raise CustomHTTPException(404, "Item not found")
    res = execute_middleware_chain(failing_handler, {})
    assert res == {"status": 404, "detail": "Item not found"}

def test_oracle_negative_unhandled_exception():
    def boom_handler(req):
        raise RuntimeError("Crash")
    res = execute_middleware_chain(boom_handler, {})
    assert res == {"status": 500, "error": "Internal Server Error"}

def test_oracle_boundary_various_status_codes():
    for code in [400, 401, 403, 422]:
        def handler(req, c=code):
            raise CustomHTTPException(c, f"Error {c}")
        res = execute_middleware_chain(handler, {})
        assert res == {"status": code, "detail": f"Error {code}"}

def test_oracle_invariants_response_dict():
    res = execute_middleware_chain(lambda req: {"custom": 123}, {})
    assert isinstance(res, dict)
