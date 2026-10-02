"""
AegisBench v2 MLVerify Expansion: Category D Task Definitions
Focus: Regression Defects / API Contract Break (Tasks 069 - 074)
"""

TASKS_CAT_D = [
    {
        "id": "task_069_http_status_enum_backward_compat",
        "category": "regression_defect",
        "difficulty": "medium",
        "desc": "Ensure HTTPStatus type maintains int inheritance and integer comparisons for backward compatibility",
        "expected": "HTTPStatus instance compares equal to int (status == 200) and supports int() conversion",
        "tags": ["http", "enum", "backward-compatibility"],
        "repo": "https://github.com/aegis-benchmark/http-core",
        "commit": "2334455667788990011223344556677889900112",
        "buggy_code": '''class HTTPStatus:
    # BUG: Pure class without int inheritance or int comparison methods breaks existing callers
    def __init__(self, code: int, name: str):
        self.code = code
        self.name = name

    def __repr__(self):
        return f"<HTTPStatus {self.code}: {self.name}>"

OK = HTTPStatus(200, "OK")
NOT_FOUND = HTTPStatus(404, "NOT_FOUND")
''',
        "fixed_code": '''from enum import IntEnum

class HTTPStatus(IntEnum):
    OK = 200
    NOT_FOUND = 404

    def __repr__(self):
        return f"<HTTPStatus {self.value}: {self.name}>"

OK = HTTPStatus.OK
NOT_FOUND = HTTPStatus.NOT_FOUND
''',
        "test_code": '''import pytest
from solution import OK, NOT_FOUND

def test_status_representation():
    assert "200" in repr(OK)
    assert "OK" in repr(OK)
''',
        "hidden_test_code": '''import pytest
from solution import OK, NOT_FOUND

def test_integer_comparison_backward_compat():
    assert OK == 200
    assert NOT_FOUND == 404
    assert OK != 404

def test_int_conversion():
    assert int(OK) == 200
    assert OK < 300
''',
        "oracle_test_code": '''import pytest
from solution import OK, NOT_FOUND, HTTPStatus

def test_oracle_status_properties():
    assert issubclass(HTTPStatus, int)
    assert OK == 200
    assert hash(OK) == hash(200)
''',
        "behavioral_spec": "HTTPStatus must maintain integer identity and comparison parity for existing client code."
    },
    {
        "id": "task_070_config_merge_env_override",
        "category": "regression_defect",
        "difficulty": "medium",
        "desc": "Implement recursive deep merge for application config to avoid dropping sibling keys",
        "expected": "Overriding a nested key retains non-overridden sibling keys in the dictionary",
        "tags": ["config", "deep-merge", "regression"],
        "repo": "https://github.com/aegis-benchmark/app-config",
        "commit": "3445566778899001122334455667788990011223",
        "buggy_code": '''from typing import Any, Dict

def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merges override dictionary into base dictionary."""
    result = dict(base)
    # BUG: Shallow update overwrites nested dictionaries completely
    result.update(override)
    return result
''',
        "fixed_code": '''from typing import Any, Dict

def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges override dictionary into base dictionary."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = merge_configs(result[k], v)
        else:
            result[k] = v
    return result
''',
        "test_code": '''import pytest
from solution import merge_configs

def test_flat_merge():
    base = {"env": "prod", "retries": 3}
    override = {"retries": 5}
    res = merge_configs(base, override)
    assert res["retries"] == 5
    assert res["env"] == "prod"
''',
        "hidden_test_code": '''import pytest
from solution import merge_configs

def test_nested_dictionary_retention():
    base = {
        "db": {"host": "localhost", "port": 5432, "timeout": 30}
    }
    override = {
        "db": {"port": 5433}
    }
    res = merge_configs(base, override)
    # Port is updated
    assert res["db"]["port"] == 5433
    # Host and timeout MUST NOT be wiped out
    assert res["db"]["host"] == "localhost"
    assert res["db"]["timeout"] == 30
''',
        "oracle_test_code": '''import pytest
from solution import merge_configs

def test_oracle_deep_nesting():
    b = {"a": {"b": {"c": 1, "d": 2}}}
    o = {"a": {"b": {"c": 99}}}
    r = merge_configs(b, o)
    assert r["a"]["b"]["c"] == 99
    assert r["a"]["b"]["d"] == 2
''',
        "behavioral_spec": "Config merge must recursively preserve sibling keys in nested dictionaries."
    },
    {
        "id": "task_071_event_dispatcher_wildcard_unsubscribe",
        "category": "regression_defect",
        "difficulty": "medium",
        "desc": "Safely remove specific listener without mutating shared listener registry during dispatch",
        "expected": "Unsubscribing a listener removes only the target callback and does not break active dispatch",
        "tags": ["events", "dispatcher", "wildcard"],
        "repo": "https://github.com/aegis-benchmark/event-bus",
        "commit": "4556677889900112233445566778899001122334",
        "buggy_code": '''from collections import defaultdict
from typing import Callable, Dict, List

class EventDispatcher:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable) -> None:
        self._listeners[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        # BUG: Clears all listeners for event_name or crashes if callback missing
        if event_name in self._listeners:
            self._listeners[event_name].clear()

    def dispatch(self, event_name: str, payload: dict) -> None:
        for cb in list(self._listeners.get(event_name, [])):
            cb(payload)
''',
        "fixed_code": '''from collections import defaultdict
from typing import Callable, Dict, List

class EventDispatcher:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable) -> None:
        self._listeners[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        if event_name in self._listeners:
            try:
                self._listeners[event_name].remove(callback)
            except ValueError:
                pass

    def dispatch(self, event_name: str, payload: dict) -> None:
        for cb in list(self._listeners.get(event_name, [])):
            cb(payload)
''',
        "test_code": '''import pytest
from solution import EventDispatcher

def test_subscribe_dispatch():
    bus = EventDispatcher()
    called = []
    bus.subscribe("order.created", lambda p: called.append(p))
    bus.dispatch("order.created", {"id": 1})
    assert len(called) == 1
''',
        "hidden_test_code": '''import pytest
from solution import EventDispatcher

def test_targeted_unsubscribe():
    bus = EventDispatcher()
    calls_a = []
    calls_b = []
    cb_a = lambda p: calls_a.append(p)
    cb_b = lambda p: calls_b.append(p)
    bus.subscribe("alert", cb_a)
    bus.subscribe("alert", cb_b)
    # Unsubscribe only A
    bus.unsubscribe("alert", cb_a)
    bus.dispatch("alert", {"msg": "fire"})
    assert len(calls_a) == 0
    # B must STILL receive the event!
    assert len(calls_b) == 1
''',
        "oracle_test_code": '''import pytest
from solution import EventDispatcher

def test_oracle_missing_unsubscribe_noop():
    bus = EventDispatcher()
    cb = lambda p: None
    # Should not raise exception when unsubscribing non-existent listener
    bus.unsubscribe("unknown", cb)
''',
        "behavioral_spec": "Unsubscribing a handler must target only that handler and preserve sibling listeners."
    },
    {
        "id": "task_072_schema_validator_extra_fields_ignore",
        "category": "regression_defect",
        "difficulty": "medium",
        "desc": "Preserve backward compatibility by ignoring unknown fields in user record validator",
        "expected": "Validates declared fields and does not reject payloads containing additional attributes",
        "tags": ["validation", "schema", "backward-compatibility"],
        "repo": "https://github.com/aegis-benchmark/schema-tools",
        "commit": "5667788990011223344556677889900112233445",
        "buggy_code": '''class ValidationError(Exception):
    pass

def validate_user_payload(data: dict) -> dict:
    """Validates user payload conforming to v1 schema."""
    required_fields = {"username", "email"}
    for f in required_fields:
        if f not in data:
            raise ValidationError(f"Missing required field: {f}")

    # BUG: Forbids unknown fields, breaking backward compatibility with v2 clients sending 'tags' or 'metadata'
    allowed_fields = {"username", "email", "age"}
    extra = set(data.keys()) - allowed_fields
    if extra:
        raise ValidationError(f"Unexpected fields: {extra}")
    return data
''',
        "fixed_code": '''class ValidationError(Exception):
    pass

def validate_user_payload(data: dict) -> dict:
    """Validates user payload conforming to v1 schema."""
    required_fields = {"username", "email"}
    for f in required_fields:
        if f not in data:
            raise ValidationError(f"Missing required field: {f}")
    if not isinstance(data["username"], str) or not data["username"].strip():
        raise ValidationError("Invalid username")
    if "@" not in str(data["email"]):
        raise ValidationError("Invalid email")
    # Tolerant reader: extra fields are accepted without failing validation
    return data
''',
        "test_code": '''import pytest
from solution import validate_user_payload, ValidationError

def test_valid_user():
    data = {"username": "john", "email": "john@example.com"}
    assert validate_user_payload(data) == data

def test_missing_field():
    with pytest.raises(ValidationError):
        validate_user_payload({"username": "john"})
''',
        "hidden_test_code": '''import pytest
from solution import validate_user_payload

def test_extra_metadata_accepted():
    data = {
        "username": "john",
        "email": "john@example.com",
        "role": "admin",
        "extra_info": {"custom": 123}
    }
    # Should NOT raise ValidationError
    res = validate_user_payload(data)
    assert res["username"] == "john"
''',
        "oracle_test_code": '''import pytest
from solution import validate_user_payload, ValidationError

def test_oracle_data_integrity():
    with pytest.raises(ValidationError):
        validate_user_payload({"username": "", "email": "a@b.com"})
    with pytest.raises(ValidationError):
        validate_user_payload({"username": "valid", "email": "invalid_email"})
''',
        "behavioral_spec": "Schema validator must accept extra fields gracefully to maintain API client compatibility."
    },
    {
        "id": "task_073_pagination_cursor_opaque_encoding",
        "category": "regression_defect",
        "difficulty": "medium",
        "desc": "Support backward compatibility for legacy integer offset cursor strings",
        "expected": "decode_cursor parses base64 JSON tokens as well as plain legacy integer offset strings",
        "tags": ["pagination", "cursor", "backward-compatibility"],
        "repo": "https://github.com/aegis-benchmark/api-paginate",
        "commit": "6778899001122334455667788990011223344556",
        "buggy_code": '''import base64
import json

def decode_cursor(cursor_token: str) -> int:
    """Decodes cursor token into integer record offset."""
    # BUG: Assumes cursor is always base64 JSON, failing on legacy integer string offsets like '50'
    raw = base64.b64decode(cursor_token.encode()).decode()
    data = json.loads(raw)
    return int(data["offset"])
''',
        "fixed_code": '''import base64
import json

def decode_cursor(cursor_token: str) -> int:
    """Decodes cursor token into integer record offset with legacy fallback."""
    if not cursor_token:
        return 0
    # Try legacy integer string first
    if cursor_token.isdigit():
        return int(cursor_token)
    try:
        raw = base64.b64decode(cursor_token.encode()).decode()
        data = json.loads(raw)
        return int(data.get("offset", 0))
    except Exception:
        raise ValueError(f"Invalid cursor format: {cursor_token}")
''',
        "test_code": '''import base64
import json
import pytest
from solution import decode_cursor

def test_opaque_b64_cursor():
    token = base64.b64encode(json.dumps({"offset": 25}).encode()).decode()
    assert decode_cursor(token) == 25
''',
        "hidden_test_code": '''import pytest
from solution import decode_cursor

def test_legacy_integer_offset_string():
    assert decode_cursor("50") == 50
    assert decode_cursor("0") == 0

def test_invalid_cursor_raises():
    with pytest.raises(ValueError):
        decode_cursor("invalid_payload_!@#$")
''',
        "oracle_test_code": '''import pytest
from solution import decode_cursor

def test_oracle_empty_token_zero():
    assert decode_cursor("") == 0
''',
        "behavioral_spec": "Pagination cursor decoder must retain backward-compatible parsing of legacy integer offset strings."
    },
    {
        "id": "task_074_logging_format_context_pollution",
        "category": "regression_defect",
        "difficulty": "medium",
        "desc": "Handle missing or cleared contextvar in logging record formatter without crashing",
        "expected": "Formats record with fallback '-' when request_id contextvar is None or unset",
        "tags": ["logging", "contextvars", "formatting"],
        "repo": "https://github.com/aegis-benchmark/log-framework",
        "commit": "7889900112233445566778899001122334455667",
        "buggy_code": '''import contextvars

request_id_var = contextvars.ContextVar("request_id", default=None)

def format_log_entry(level: str, message: str) -> str:
    req_id = request_id_var.get()
    # BUG: Fails with TypeError if req_id is None, instead of substituting default placeholder
    return f"[{level}] [req:{req_id.upper()}] {message}"
''',
        "fixed_code": '''import contextvars

request_id_var = contextvars.ContextVar("request_id", default=None)

def format_log_entry(level: str, message: str) -> str:
    req_id = request_id_var.get()
    tag = req_id.upper() if req_id else "-"
    return f"[{level}] [req:{tag}] {message}"
''',
        "test_code": '''import pytest
from solution import format_log_entry, request_id_var

def test_log_entry_with_request_id():
    token = request_id_var.set("req_123")
    try:
        entry = format_log_entry("INFO", "Operation succeeded")
        assert "[req:REQ_123]" in entry
    finally:
        request_id_var.reset(token)
''',
        "hidden_test_code": '''import pytest
from solution import format_log_entry, request_id_var

def test_log_entry_without_request_id():
    token = request_id_var.set(None)
    try:
        entry = format_log_entry("WARN", "No context present")
        assert "[req:-]" in entry
    finally:
        request_id_var.reset(token)
''',
        "oracle_test_code": '''import pytest
from solution import format_log_entry

def test_oracle_default_uninitialized_context():
    # Fresh execution without setting contextvar
    entry = format_log_entry("ERROR", "Unhandled error")
    assert "[ERROR]" in entry
    assert "[req:-]" in entry
''',
        "behavioral_spec": "Log formatter must safely handle missing contextual tokens with placeholder fallbacks."
    }
]
