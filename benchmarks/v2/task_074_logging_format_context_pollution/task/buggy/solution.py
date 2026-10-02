import contextvars

request_id_var = contextvars.ContextVar("request_id", default=None)

def format_log_entry(level: str, message: str) -> str:
    req_id = request_id_var.get()
    # BUG: Fails with TypeError if req_id is None, instead of substituting default placeholder
    return f"[{level}] [req:{req_id.upper()}] {message}"
