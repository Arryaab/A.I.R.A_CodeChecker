from solution import execute_middleware_chain, CustomHTTPException

def generic_failing_handler(req):
    raise ValueError("unexpected crash")

def test_middleware_catches_generic_exception():
    res = execute_middleware_chain(generic_failing_handler, {})
    assert res == {"status": 500, "error": "Internal Server Error"}
