class HTTPStatus:
    # BUG: Pure class without int inheritance or int comparison methods breaks existing callers
    def __init__(self, code: int, name: str):
        self.code = code
        self.name = name

    def __repr__(self):
        return f"<HTTPStatus {self.code}: {self.name}>"

OK = HTTPStatus(200, "OK")
NOT_FOUND = HTTPStatus(404, "NOT_FOUND")
