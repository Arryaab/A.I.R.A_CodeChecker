class CustomHTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

def execute_middleware_chain(handler, request):
    try:
        return handler(request)
    except Exception as exc:
        # BUG: re-raises CustomHTTPException instead of formatting dict response
        if isinstance(exc, CustomHTTPException):
            raise exc
        return {"status": 500, "error": "Internal Server Error"}
