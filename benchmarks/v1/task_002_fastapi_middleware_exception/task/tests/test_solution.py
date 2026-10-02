from solution import execute_middleware_chain, CustomHTTPException

def failing_handler(req):
    raise CustomHTTPException(404, "Item not found")

def test_middleware_catches_http_exception():
    res = execute_middleware_chain(failing_handler, {})
    assert res == {"status": 404, "detail": "Item not found"}
