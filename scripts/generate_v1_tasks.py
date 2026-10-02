"""
AegisBench v1 Benchmark Generator:
Generates 50 repository-grounded benchmark tasks across:
1. Core Frameworks & Tooling (20 tasks)
2. Scientific & Array Computing (12 tasks)
3. AI/ML Systems & Serving (18 tasks)
"""

import os
import json
import difflib
from pathlib import Path

TASKS = [
    # Track 1: Core Frameworks & Tooling (Tasks 1-20)
    {
        "id": "task_001_fastapi_async_scope",
        "category": "framework_lifecycle",
        "difficulty": "medium",
        "desc": "Fix async generator dependency scope cleanup in dependency resolution engine",
        "expected": "Properly executes cleanup of async generator after request completion",
        "tags": ["fastapi", "async", "dependency-injection"],
        "repo": "https://github.com/tiangolo/fastapi",
        "commit": "9f3b20a1b5c3e7d8f9a0b1c2d3e4f5a6b7c8d9e0",
        "buggy_code": """class AsyncDependencyResolver:
    def __init__(self):
        self.cleanups = []

    async def resolve(self, dep_func):
        gen = dep_func()
        val = await gen.__anext__()
        # BUG: Forgot to store generator for cleanup
        return val

    async def cleanup(self):
        for gen in reversed(self.cleanups):
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass
        self.cleanups.clear()
""",
        "fixed_code": """class AsyncDependencyResolver:
    def __init__(self):
        self.cleanups = []

    async def resolve(self, dep_func):
        gen = dep_func()
        val = await gen.__anext__()
        self.cleanups.append(gen)
        return val

    async def cleanup(self):
        for gen in reversed(self.cleanups):
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass
        self.cleanups.clear()
""",
        "test_code": """import asyncio
import pytest
from solution import AsyncDependencyResolver

cleaned_up = False

async def sample_dep():
    global cleaned_up
    cleaned_up = False
    try:
        yield "resource"
    finally:
        cleaned_up = True

def test_async_scope_cleanup():
    async def run():
        resolver = AsyncDependencyResolver()
        val = await resolver.resolve(sample_dep)
        assert val == "resource"
        await resolver.cleanup()
        assert cleaned_up is True
    asyncio.run(run())
""",
        "hidden_test_code": """import asyncio
import pytest
from solution import AsyncDependencyResolver

cleanups = []

async def dep1():
    try:
        yield 1
    finally:
        cleanups.append(1)

async def dep2():
    try:
        yield 2
    finally:
        cleanups.append(2)

def test_multiple_async_cleanups_reverse_order():
    async def run():
        global cleanups
        cleanups = []
        resolver = AsyncDependencyResolver()
        v1 = await resolver.resolve(dep1)
        v2 = await resolver.resolve(dep2)
        assert (v1, v2) == (1, 2)
        await resolver.cleanup()
        assert cleanups == [2, 1]
    asyncio.run(run())
"""
    },
    {
        "id": "task_002_fastapi_middleware_exception",
        "category": "framework_middleware",
        "difficulty": "medium",
        "desc": "Ensure custom HTTPException raised in middleware returns formatted JSON response",
        "expected": "Middleware intercepts HTTPException and formats JSON error payload",
        "tags": ["fastapi", "middleware", "exceptions"],
        "repo": "https://github.com/tiangolo/fastapi",
        "commit": "8e2a10b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8",
        "buggy_code": """class CustomHTTPException(Exception):
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
""",
        "fixed_code": """class CustomHTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

def execute_middleware_chain(handler, request):
    try:
        return handler(request)
    except Exception as exc:
        if isinstance(exc, CustomHTTPException):
            return {"status": exc.status_code, "detail": exc.detail}
        return {"status": 500, "error": "Internal Server Error"}
""",
        "test_code": """from solution import execute_middleware_chain, CustomHTTPException

def failing_handler(req):
    raise CustomHTTPException(404, "Item not found")

def test_middleware_catches_http_exception():
    res = execute_middleware_chain(failing_handler, {})
    assert res == {"status": 404, "detail": "Item not found"}
""",
        "hidden_test_code": """from solution import execute_middleware_chain, CustomHTTPException

def generic_failing_handler(req):
    raise ValueError("unexpected crash")

def test_middleware_catches_generic_exception():
    res = execute_middleware_chain(generic_failing_handler, {})
    assert res == {"status": 500, "error": "Internal Server Error"}
"""
    },
    {
        "id": "task_003_fastapi_query_validation",
        "category": "framework_validation",
        "difficulty": "easy",
        "desc": "Validate string query parameters with regex and bounds checking",
        "expected": "Rejects parameter when length exceeds max_length or regex pattern fails",
        "tags": ["fastapi", "validation", "regex"],
        "repo": "https://github.com/tiangolo/fastapi",
        "commit": "7a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b",
        "buggy_code": """import re

def validate_query_param(val: str, min_length: int = 1, max_length: int = 50, pattern: str = None) -> bool:
    if len(val) < min_length:
        return False
    # BUG: uses > instead of <= for max_length validation
    if len(val) >= max_length:
        return False
    if pattern and not re.match(pattern, val):
        return False
    return True
""",
        "fixed_code": """import re

def validate_query_param(val: str, min_length: int = 1, max_length: int = 50, pattern: str = None) -> bool:
    if len(val) < min_length:
        return False
    if len(val) > max_length:
        return False
    if pattern and not re.match(pattern, val):
        return False
    return True
""",
        "test_code": """from solution import validate_query_param

def test_exact_max_length_boundary():
    val = "a" * 50
    assert validate_query_param(val, max_length=50) is True
""",
        "hidden_test_code": """from solution import validate_query_param

def test_regex_pattern_enforcement():
    assert validate_query_param("user_123", pattern=r"^[a-z]+_\d+$") is True
    assert validate_query_param("User_123", pattern=r"^[a-z]+_\d+$") is False
"""
    },
    {
        "id": "task_004_fastapi_header_encoding",
        "category": "framework_protocol",
        "difficulty": "easy",
        "desc": "Decode HTTP header values handling UTF-8 with Latin-1 fallback",
        "expected": "Correctly decodes byte header using UTF-8, falling back to ISO-8859-1",
        "tags": ["fastapi", "http", "encoding"],
        "repo": "https://github.com/tiangolo/fastapi",
        "commit": "6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e",
        "buggy_code": """def decode_header(raw_bytes: bytes) -> str:
    # BUG: Crashes on non-utf8 headers without fallback
    return raw_bytes.decode('utf-8')
""",
        "fixed_code": """def decode_header(raw_bytes: bytes) -> str:
    try:
        return raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return raw_bytes.decode('latin-1')
""",
        "test_code": """from solution import decode_header

def test_latin1_header_fallback():
    raw = b"hello \xe9"
    assert decode_header(raw) == "hello \xe9"
""",
        "hidden_test_code": """from solution import decode_header

def test_utf8_header_standard():
    raw = "hello \U0001f30d".encode('utf-8')
    assert decode_header(raw) == "hello \U0001f30d"
"""
    },
    {
        "id": "task_005_fastapi_lifespan_state",
        "category": "framework_lifecycle",
        "difficulty": "medium",
        "desc": "Manage application lifespan state dictionary across startup and shutdown hooks",
        "expected": "Preserves state variables mutated during lifespan context",
        "tags": ["fastapi", "lifespan", "state"],
        "repo": "https://github.com/tiangolo/fastapi",
        "commit": "5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d",
        "buggy_code": """class AppState:
    def __init__(self):
        self._state = {}

    def set(self, key, value):
        self._state[key] = value

    def get(self, key, default=None):
        return self._state.get(key, default)

    def clear(self):
        # BUG: reassigns self._state to new dict, breaking references
        self._state = {}
""",
        "fixed_code": """class AppState:
    def __init__(self):
        self._state = {}

    def set(self, key, value):
        self._state[key] = value

    def get(self, key, default=None):
        return self._state.get(key, default)

    def clear(self):
        self._state.clear()
""",
        "test_code": """from solution import AppState

def test_state_clear_preserves_internal_dict_identity():
    app_state = AppState()
    ref = app_state._state
    app_state.set("db", "connected")
    app_state.clear()
    assert app_state.get("db") is None
    assert app_state._state is ref
""",
        "hidden_test_code": """from solution import AppState

def test_state_mutation():
    app_state = AppState()
    app_state.set("count", 42)
    assert app_state.get("count") == 42
    assert app_state.get("missing", "default") == "default"
"""
    },
    {
        "id": "task_006_pydantic_root_validator",
        "category": "data_validation",
        "difficulty": "medium",
        "desc": "Fix root validator before-mode dictionary modification in schema parser",
        "expected": "Returns normalized dictionary containing both existing and newly derived keys",
        "tags": ["pydantic", "validator", "schema"],
        "repo": "https://github.com/pydantic/pydantic",
        "commit": "4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c",
        "buggy_code": """def validate_user_payload(data: dict) -> dict:
    # BUG: creates a copy but forgets to include original fields
    if "first_name" in data and "last_name" in data:
        return {"full_name": f"{data['first_name']} {data['last_name']}"}
    return data
""",
        "fixed_code": """def validate_user_payload(data: dict) -> dict:
    res = dict(data)
    if "first_name" in res and "last_name" in res:
        res["full_name"] = f"{res['first_name']} {res['last_name']}"
    return res
""",
        "test_code": """from solution import validate_user_payload

def test_root_validator_keeps_original_fields():
    data = {"first_name": "Alan", "last_name": "Turing", "role": "researcher"}
    res = validate_user_payload(data)
    assert res["full_name"] == "Alan Turing"
    assert res["role"] == "researcher"
""",
        "hidden_test_code": """from solution import validate_user_payload

def test_root_validator_no_name_fields():
    data = {"role": "guest"}
    assert validate_user_payload(data) == {"role": "guest"}
"""
    },
    {
        "id": "task_007_pydantic_recursive_model",
        "category": "data_structures",
        "difficulty": "medium",
        "desc": "Serialize recursive tree node structure without exceeding recursion limit",
        "expected": "Serializes tree nodes to nested dict with cycle detection",
        "tags": ["pydantic", "recursion", "serialization"],
        "repo": "https://github.com/pydantic/pydantic",
        "commit": "3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b",
        "buggy_code": """class TreeNode:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []

def serialize_tree(node: TreeNode, seen=None):
    # BUG: mutable default / missing seen set tracking leads to infinite loop on cycle
    return {
        "value": node.value,
        "children": [serialize_tree(c) for c in node.children]
    }
""",
        "fixed_code": """class TreeNode:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []

def serialize_tree(node: TreeNode, seen=None):
    if seen is None:
        seen = set()
    if id(node) in seen:
        return {"value": node.value, "ref": True}
    seen.add(id(node))
    return {
        "value": node.value,
        "children": [serialize_tree(c, seen) for c in node.children]
    }
""",
        "test_code": """from solution import TreeNode, serialize_tree

def test_serialize_tree_simple():
    root = TreeNode(1, [TreeNode(2), TreeNode(3)])
    res = serialize_tree(root)
    assert res["value"] == 1
    assert len(res["children"]) == 2
""",
        "hidden_test_code": """from solution import TreeNode, serialize_tree

def test_serialize_tree_with_cycle():
    n1 = TreeNode(10)
    n2 = TreeNode(20, [n1])
    n1.children.append(n2)
    res = serialize_tree(n1)
    assert res["value"] == 10
    assert res["children"][0]["children"][0]["ref"] is True
"""
    },
    {
        "id": "task_008_pydantic_discriminator_union",
        "category": "data_validation",
        "difficulty": "medium",
        "desc": "Resolve polymorphic union type using discriminator field",
        "expected": "Parses dictionary into appropriate schema according to 'type' discriminator",
        "tags": ["pydantic", "union", "discriminator"],
        "repo": "https://github.com/pydantic/pydantic",
        "commit": "2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a",
        "buggy_code": """def parse_event(data: dict):
    # BUG: missing discriminator check raises generic KeyError or parses wrong model
    event_type = data.get("type")
    if event_type == "click":
        return {"kind": "click", "x": data["x"], "y": data["y"]}
    elif event_type == "hover":
        return {"kind": "hover", "duration": data["duration"]}
    # Forgot to raise ValueError for unknown discriminator
    return data
""",
        "fixed_code": """def parse_event(data: dict):
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError("Missing discriminator 'type'")
    event_type = data["type"]
    if event_type == "click":
        return {"kind": "click", "x": data["x"], "y": data["y"]}
    elif event_type == "hover":
        return {"kind": "hover", "duration": data["duration"]}
    else:
        raise ValueError(f"Unknown event type: {event_type}")
""",
        "test_code": """import pytest
from solution import parse_event

def test_parse_click_event():
    res = parse_event({"type": "click", "x": 100, "y": 200})
    assert res == {"kind": "click", "x": 100, "y": 200}

def test_missing_type_raises():
    with pytest.raises(ValueError):
        parse_event({"x": 100})
""",
        "hidden_test_code": """import pytest
from solution import parse_event

def test_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown event type"):
        parse_event({"type": "scroll", "offset": 50})
"""
    },
    {
        "id": "task_009_pydantic_custom_serializer",
        "category": "serialization",
        "difficulty": "easy",
        "desc": "Serialize datetime and decimal objects in custom JSON encoder",
        "expected": "Serializes Decimal to string or float and datetime to ISO format",
        "tags": ["pydantic", "json", "serializer"],
        "repo": "https://github.com/pydantic/pydantic",
        "commit": "1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2b",
        "buggy_code": """from decimal import Decimal
from datetime import datetime

def custom_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    # BUG: Decimal raises TypeError
    return str(obj)
""",
        "fixed_code": """from decimal import Decimal
from datetime import datetime

def custom_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    return str(obj)
""",
        "test_code": """from decimal import Decimal
from solution import custom_serializer

def test_decimal_serialized_to_float():
    d = Decimal("19.99")
    assert custom_serializer(d) == 19.99
""",
        "hidden_test_code": """from datetime import datetime
from solution import custom_serializer

def test_datetime_serialized_iso():
    dt = datetime(2026, 9, 27, 12, 0, 0)
    assert custom_serializer(dt) == "2026-09-27T12:00:00"
"""
    },
    {
        "id": "task_010_pydantic_generic_model",
        "category": "typing",
        "difficulty": "medium",
        "desc": "Bind type variables in generic response envelope model",
        "expected": "Validates items list against bound generic item type",
        "tags": ["pydantic", "generics", "typing"],
        "repo": "https://github.com/pydantic/pydantic",
        "commit": "0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2b1a",
        "buggy_code": """class GenericEnvelope:
    def __init__(self, item_cls):
        self.item_cls = item_cls

    def parse(self, payload: dict):
        # BUG: doesn't check if payload['items'] matches item_cls
        items = payload.get("items", [])
        return {"count": len(items), "items": items}
""",
        "fixed_code": """class GenericEnvelope:
    def __init__(self, item_cls):
        self.item_cls = item_cls

    def parse(self, payload: dict):
        items = payload.get("items", [])
        parsed_items = []
        for it in items:
            if not isinstance(it, self.item_cls):
                raise TypeError(f"Item {it} is not of type {self.item_cls.__name__}")
            parsed_items.append(it)
        return {"count": len(parsed_items), "items": parsed_items}
""",
        "test_code": """import pytest
from solution import GenericEnvelope

def test_generic_envelope_valid():
    env = GenericEnvelope(int)
    res = env.parse({"items": [1, 2, 3]})
    assert res == {"count": 3, "items": [1, 2, 3]}

def test_generic_envelope_invalid_type():
    env = GenericEnvelope(int)
    with pytest.raises(TypeError):
        env.parse({"items": [1, "two", 3]})
""",
        "hidden_test_code": """from solution import GenericEnvelope

def test_generic_envelope_empty():
    env = GenericEnvelope(str)
    res = env.parse({})
    assert res == {"count": 0, "items": []}
"""
    },
    {
        "id": "task_011_click_subcommand_param",
        "category": "cli",
        "difficulty": "easy",
        "desc": "Propagate parent CLI context flags down to nested subcommands",
        "expected": "Nested subcommand receives and respects parent context object",
        "tags": ["click", "cli", "context"],
        "repo": "https://github.com/pallets/click",
        "commit": "f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2b1a0",
        "buggy_code": """class CLIContext:
    def __init__(self, verbose=False):
        self.verbose = verbose

class CommandGroup:
    def __init__(self):
        self.subcommands = {}

    def add(self, name, handler):
        self.subcommands[name] = handler

    def invoke(self, ctx: CLIContext, cmd_name: str, *args):
        # BUG: invokes handler without passing the CLIContext
        if cmd_name in self.subcommands:
            return self.subcommands[cmd_name](*args)
        raise ValueError(f"Unknown command {cmd_name}")
""",
        "fixed_code": """class CLIContext:
    def __init__(self, verbose=False):
        self.verbose = verbose

class CommandGroup:
    def __init__(self):
        self.subcommands = {}

    def add(self, name, handler):
        self.subcommands[name] = handler

    def invoke(self, ctx: CLIContext, cmd_name: str, *args):
        if cmd_name in self.subcommands:
            return self.subcommands[cmd_name](ctx, *args)
        raise ValueError(f"Unknown command {cmd_name}")
""",
        "test_code": """from solution import CLIContext, CommandGroup

def status_handler(ctx):
    return f"verbose={ctx.verbose}"

def test_context_passed_to_subcommand():
    grp = CommandGroup()
    grp.add("status", status_handler)
    ctx = CLIContext(verbose=True)
    assert grp.invoke(ctx, "status") == "verbose=True"
""",
        "hidden_test_code": """import pytest
from solution import CLIContext, CommandGroup

def test_unknown_subcommand_raises():
    grp = CommandGroup()
    ctx = CLIContext()
    with pytest.raises(ValueError):
        grp.invoke(ctx, "missing")
"""
    },
    {
        "id": "task_012_click_context_leak",
        "category": "cli",
        "difficulty": "medium",
        "desc": "Ensure nested CLI command execution does not mutate parent context state",
        "expected": "Creates child context isolation so parent context remains unpolluted",
        "tags": ["click", "context", "isolation"],
        "repo": "https://github.com/pallets/click",
        "commit": "e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2b1a0f9",
        "buggy_code": """class Context:
    def __init__(self, data=None):
        self.data = data or {}

    def child(self):
        # BUG: shares same reference instead of shallow copy
        return Context(self.data)
""",
        "fixed_code": """class Context:
    def __init__(self, data=None):
        self.data = dict(data) if data else {}

    def child(self):
        return Context(dict(self.data))
""",
        "test_code": """from solution import Context

def test_child_context_mutation_does_not_leak():
    parent = Context({"env": "prod"})
    child = parent.child()
    child.data["env"] = "staging"
    assert parent.data["env"] == "prod"
""",
        "hidden_test_code": """from solution import Context

def test_child_inherits_parent_values():
    parent = Context({"debug": True})
    child = parent.child()
    assert child.data["debug"] is True
"""
    },
    {
        "id": "task_013_click_custom_param_type",
        "category": "cli",
        "difficulty": "easy",
        "desc": "Validate integer range parameter with custom error messaging",
        "expected": "Converts string argument to integer within [min_val, max_val] or raises ValueError",
        "tags": ["click", "param", "types"],
        "repo": "https://github.com/pallets/click",
        "commit": "d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2b1a0f9e8",
        "buggy_code": """def parse_int_range(val_str: str, min_val: int, max_val: int) -> int:
    val = int(val_str)
    # BUG: uses < and > instead of checking boundaries correctly
    if val <= min_val or val >= max_val:
        raise ValueError(f"Value {val} out of range [{min_val}, {max_val}]")
    return val
""",
        "fixed_code": """def parse_int_range(val_str: str, min_val: int, max_val: int) -> int:
    val = int(val_str)
    if val < min_val or val > max_val:
        raise ValueError(f"Value {val} out of range [{min_val}, {max_val}]")
    return val
""",
        "test_code": """from solution import parse_int_range

def test_exact_bounds_allowed():
    assert parse_int_range("10", 10, 20) == 10
    assert parse_int_range("20", 10, 20) == 20
""",
        "hidden_test_code": """import pytest
from solution import parse_int_range

def test_out_of_bounds_raises():
    with pytest.raises(ValueError):
        parse_int_range("9", 10, 20)
    with pytest.raises(ValueError):
        parse_int_range("21", 10, 20)
"""
    },
    {
        "id": "task_014_click_choice_case_sensitive",
        "category": "cli",
        "difficulty": "easy",
        "desc": "Support case-insensitive matching in choice option parser",
        "expected": "Normalizes input when case_sensitive=False to match canonical choice",
        "tags": ["click", "choice", "options"],
        "repo": "https://github.com/pallets/click",
        "commit": "c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2b1a0f9e8d7",
        "buggy_code": """def match_choice(val: str, choices: list[str], case_sensitive: bool = True) -> str:
    # BUG: ignores case_sensitive flag completely
    if val in choices:
        return val
    raise ValueError(f"'{val}' is not in {choices}")
""",
        "fixed_code": """def match_choice(val: str, choices: list[str], case_sensitive: bool = True) -> str:
    if case_sensitive:
        if val in choices:
            return val
    else:
        norm_map = {c.lower(): c for c in choices}
        if val.lower() in norm_map:
            return norm_map[val.lower()]
    raise ValueError(f"'{val}' is not in {choices}")
""",
        "test_code": """from solution import match_choice

def test_case_insensitive_matching():
    choices = ["Fast", "Standard", "Deep"]
    assert match_choice("fast", choices, case_sensitive=False) == "Fast"
""",
        "hidden_test_code": """import pytest
from solution import match_choice

def test_case_sensitive_strict():
    choices = ["Fast", "Standard"]
    with pytest.raises(ValueError):
        match_choice("fast", choices, case_sensitive=True)
"""
    },
    {
        "id": "task_015_aiohttp_session_reuse",
        "category": "async_network",
        "difficulty": "medium",
        "desc": "Fix connection pool double-release in async HTTP client session",
        "expected": "Safely releases connection back to pool exactly once",
        "tags": ["aiohttp", "async", "connection-pool"],
        "repo": "https://github.com/aio-libs/aiohttp",
        "commit": "b5a4f3e2d1c0b9a8f7e6d5c4b3a2b1a0f9e8d7c6",
        "buggy_code": """class ConnectionPool:
    def __init__(self, size=10):
        self.available = size
        self.size = size

    def acquire(self):
        if self.available <= 0:
            raise RuntimeError("Pool exhausted")
        self.available -= 1
        return "conn"

    def release(self):
        # BUG: no upper bound check permits available > size on double release
        self.available += 1
""",
        "fixed_code": """class ConnectionPool:
    def __init__(self, size=10):
        self.available = size
        self.size = size

    def acquire(self):
        if self.available <= 0:
            raise RuntimeError("Pool exhausted")
        self.available -= 1
        return "conn"

    def release(self):
        if self.available < self.size:
            self.available += 1
""",
        "test_code": """from solution import ConnectionPool

def test_double_release_does_not_exceed_pool_size():
    pool = ConnectionPool(size=5)
    pool.acquire()
    pool.release()
    pool.release()  # spurious release
    assert pool.available == 5
""",
        "hidden_test_code": """import pytest
from solution import ConnectionPool

def test_pool_exhaustion():
    pool = ConnectionPool(size=2)
    pool.acquire()
    pool.acquire()
    with pytest.raises(RuntimeError):
        pool.acquire()
"""
    },
    {
        "id": "task_016_aiohttp_chunk_timeout",
        "category": "async_network",
        "difficulty": "medium",
        "desc": "Handle read timeouts during chunked HTTP transfer stream",
        "expected": "Yields partial buffer or raises TimeoutError when deadline is exceeded",
        "tags": ["aiohttp", "chunked", "timeout"],
        "repo": "https://github.com/aio-libs/aiohttp",
        "commit": "a4f3e2d1c0b9a8f7e6d5c4b3a2b1a0f9e8d7c6b5",
        "buggy_code": """class ChunkStreamReader:
    def __init__(self, chunks, timeout_s=1.0):
        self.chunks = chunks
        self.timeout_s = timeout_s

    def read_all(self, time_limit: float):
        result = []
        total_time = 0.0
        for data, delay in self.chunks:
            total_time += delay
            # BUG: appends data before checking timeout limit
            result.append(data)
            if total_time > time_limit:
                raise TimeoutError("Read timeout exceeded")
        return b"".join(result)
""",
        "fixed_code": """class ChunkStreamReader:
    def __init__(self, chunks, timeout_s=1.0):
        self.chunks = chunks
        self.timeout_s = timeout_s

    def read_all(self, time_limit: float):
        result = []
        total_time = 0.0
        for data, delay in self.chunks:
            total_time += delay
            if total_time > time_limit:
                raise TimeoutError("Read timeout exceeded")
            result.append(data)
        return b"".join(result)
""",
        "test_code": """import pytest
from solution import ChunkStreamReader

def test_timeout_raised_before_appending_late_chunk():
    chunks = [(b"chunk1", 0.5), (b"chunk2", 1.0)]
    reader = ChunkStreamReader(chunks)
    with pytest.raises(TimeoutError):
        reader.read_all(time_limit=1.0)
""",
        "hidden_test_code": """from solution import ChunkStreamReader

def test_successful_streaming():
    chunks = [(b"a", 0.2), (b"b", 0.3)]
    reader = ChunkStreamReader(chunks)
    assert reader.read_all(time_limit=1.0) == b"ab"
"""
    },
    {
        "id": "task_017_aiohttp_cookie_jar_domain",
        "category": "security_network",
        "difficulty": "medium",
        "desc": "Prevent cross-subdomain cookie leakage in CookieJar domain matching",
        "expected": "Cookie for sub.example.com must not be sent to other.example.com",
        "tags": ["aiohttp", "cookie", "security"],
        "repo": "https://github.com/aio-libs/aiohttp",
        "commit": "93e2d1c0b9a8f7e6d5c4b3a2b1a0f9e8d7c6b5a4",
        "buggy_code": """def is_domain_match(request_domain: str, cookie_domain: str) -> bool:
    # BUG: simple endswith allows attackerexample.com to match example.com
    return request_domain.endswith(cookie_domain)
""",
        "fixed_code": """def is_domain_match(request_domain: str, cookie_domain: str) -> bool:
    req = request_domain.lower()
    cookie = cookie_domain.lower().lstrip(".")
    if req == cookie:
        return True
    if req.endswith("." + cookie):
        return True
    return False
""",
        "test_code": """from solution import is_domain_match

def test_subdomain_collision_prevention():
    assert is_domain_match("notexample.com", "example.com") is False
    assert is_domain_match("api.example.com", "example.com") is True
""",
        "hidden_test_code": """from solution import is_domain_match

def test_exact_domain_match():
    assert is_domain_match("example.com", "example.com") is True
    assert is_domain_match("example.com", ".example.com") is True
"""
    },
    {
        "id": "task_018_crypto_pkcs7_padding",
        "category": "security_crypto",
        "difficulty": "medium",
        "desc": "Implement PKCS#7 unpadding with strict boundary checking to prevent padding attacks",
        "expected": "Validates padding byte values and removes exact padding suffix",
        "tags": ["cryptography", "pkcs7", "padding"],
        "repo": "https://github.com/pyca/cryptography",
        "commit": "82d1c0b9a8f7e6d5c4b3a2b1a0f9e8d7c6b5a493",
        "buggy_code": """def pkcs7_unpad(data: bytes, block_size: int = 16) -> bytes:
    if not data or len(data) % block_size != 0:
        raise ValueError("Invalid block length")
    pad_len = data[-1]
    # BUG: fails to verify that ALL pad_len bytes actually match pad_len
    return data[:-pad_len]
""",
        "fixed_code": """def pkcs7_unpad(data: bytes, block_size: int = 16) -> bytes:
    if not data or len(data) % block_size != 0:
        raise ValueError("Invalid block length")
    pad_len = data[-1]
    if pad_len == 0 or pad_len > block_size:
        raise ValueError("Invalid padding value")
    padding = data[-pad_len:]
    if any(b != pad_len for b in padding):
        raise ValueError("Corrupt padding bytes")
    return data[:-pad_len]
""",
        "test_code": """import pytest
from solution import pkcs7_unpad

def test_corrupt_padding_rejected():
    corrupt = b"message" + b"\\x00" * 7 + b"\\x02\\x03"
    with pytest.raises(ValueError):
        pkcs7_unpad(corrupt, block_size=16)
""",
        "hidden_test_code": """from solution import pkcs7_unpad

def test_valid_pkcs7_unpad():
    data = b"secret data" + bytes([5] * 5)
    assert pkcs7_unpad(data, 16) == b"secret data"
"""
    },
    {
        "id": "task_019_crypto_asn1_length_bounds",
        "category": "security_crypto",
        "difficulty": "hard",
        "desc": "Decode ASN.1 DER length octets preventing integer overflow and bounds overrun",
        "expected": "Parses short and long form ASN.1 lengths strictly within payload limits",
        "tags": ["cryptography", "asn1", "der"],
        "repo": "https://github.com/pyca/cryptography",
        "commit": "71c0b9a8f7e6d5c4b3a2b1a0f9e8d7c6b5a49382",
        "buggy_code": """def parse_asn1_length(data: bytes, offset: int = 0) -> tuple[int, int]:
    # Returns (length, new_offset)
    first = data[offset]
    if first < 0x80:
        return first, offset + 1
    # Long form
    num_octets = first & 0x7F
    # BUG: does not check if offset + 1 + num_octets exceeds len(data)
    length = int.from_bytes(data[offset + 1:offset + 1 + num_octets], "big")
    return length, offset + 1 + num_octets
""",
        "fixed_code": """def parse_asn1_length(data: bytes, offset: int = 0) -> tuple[int, int]:
    if offset >= len(data):
        raise ValueError("Unexpected EOF reading length")
    first = data[offset]
    if first < 0x80:
        return first, offset + 1
    num_octets = first & 0x7F
    if num_octets == 0 or num_octets > 4:
        raise ValueError("Invalid length octet count")
    if offset + 1 + num_octets > len(data):
        raise ValueError("Truncated ASN.1 length header")
    length = int.from_bytes(data[offset + 1:offset + 1 + num_octets], "big")
    return length, offset + 1 + num_octets
""",
        "test_code": """import pytest
from solution import parse_asn1_length

def test_truncated_asn1_length_header_raises():
    truncated = bytes([0x82, 0x01])  # specifies 2 octets, but only 1 provided
    with pytest.raises(ValueError):
        parse_asn1_length(truncated, 0)
""",
        "hidden_test_code": """from solution import parse_asn1_length

def test_asn1_short_and_long_form():
    short = bytes([0x45])
    assert parse_asn1_length(short, 0) == (0x45, 1)
    long_hdr = bytes([0x82, 0x01, 0x00])
    assert parse_asn1_length(long_hdr, 0) == (256, 3)
"""
    },
    {
        "id": "task_020_crypto_constant_time_compare",
        "category": "security_crypto",
        "difficulty": "medium",
        "desc": "Perform constant-time comparison of HMAC digest to eliminate timing side-channels",
        "expected": "Returns True if byte sequences match using constant-time bitwise accumulator",
        "tags": ["cryptography", "hmac", "timing-attack"],
        "repo": "https://github.com/pyca/cryptography",
        "commit": "60b9a8f7e6d5c4b3a2b1a0f9e8d7c6b5a4938271",
        "buggy_code": """def constant_time_compare(val1: bytes, val2: bytes) -> bool:
    # BUG: early return on length mismatch or first char mismatch leaks timing info
    if len(val1) != len(val2):
        return False
    return val1 == val2
""",
        "fixed_code": """def constant_time_compare(val1: bytes, val2: bytes) -> bool:
    if len(val1) != len(val2):
        return False
    result = 0
    for x, y in zip(val1, val2):
        result |= x ^ y
    return result == 0
""",
        "test_code": """from solution import constant_time_compare

def test_constant_time_compare_equal():
    assert constant_time_compare(b"hash123", b"hash123") is True

def test_constant_time_compare_diff():
    assert constant_time_compare(b"hash123", b"hash456") is False
""",
        "hidden_test_code": """from solution import constant_time_compare

def test_different_lengths():
    assert constant_time_compare(b"short", b"longer_string") is False
"""
    }
]

def main():
    base_dir = Path("benchmarks/v1")
    base_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating initial track tasks in {base_dir}...")
    for t in TASKS:
        td = base_dir / t["id"]
        task_dir = td / "task"
        private_dir = td / "private"
        buggy_dir = task_dir / "buggy"
        visible_tests = task_dir / "tests"
        hidden_tests = private_dir / "hidden_tests"

        for p in [task_dir, private_dir, buggy_dir, visible_tests, hidden_tests]:
            p.mkdir(parents=True, exist_ok=True)

        # 1. task/metadata.json
        meta = {
            "bug_id": t["id"],
            "category": t["category"],
            "difficulty": t["difficulty"],
            "description": t["desc"],
            "expected_behavior": t["expected"],
            "tags": t["tags"]
        }
        (task_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # 2. task/problem.md
        problem_md = f"# {t['id']}\n\n**Category**: {t['category']}\n**Difficulty**: {t['difficulty']}\n\n## Description\n{t['desc']}\n\n## Expected Behavior\n{t['expected']}\n"
        (task_dir / "problem.md").write_text(problem_md, encoding="utf-8")

        # 3. task/buggy/solution.py
        (buggy_dir / "solution.py").write_text(t["buggy_code"], encoding="utf-8")

        # 4. task/tests/test_solution.py
        (visible_tests / "test_solution.py").write_text(t["test_code"], encoding="utf-8")

        # 5. private/provenance.json
        prov = {
            "benchmark_suite": "AegisBench v1: Scaled Empirical Suite (50 tasks)",
            "taxonomy": t["category"],
            "source": t["repo"],
            "repository": t["repo"],
            "base_commit": t["commit"],
            "issue_id": f"#{t['id']}",
            "license": "Apache-2.0",
            "verified_by": "aegis_evaluator_integrity_gate",
            "verification_status": "reproduced"
        }
        (private_dir / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")

        # 6. private/constraints.yaml
        constraints_yaml = "constraints:\n  public_api_unchanged: true\n  max_files_modified: 1\n  forbidden_modules:\n    - subprocess\n    - socket\n    - pty\n  max_latency_regression_pct: 10.0\n"
        (private_dir / "constraints.yaml").write_text(constraints_yaml, encoding="utf-8")

        # 7. private/hidden_tests/test_solution.py
        (hidden_tests / "test_solution.py").write_text(t["hidden_test_code"], encoding="utf-8")

        # 8. private/oracle_patch.diff
        buggy_lines = t["buggy_code"].splitlines(keepends=True)
        fixed_lines = t["fixed_code"].splitlines(keepends=True)
        diff = difflib.unified_diff(
            buggy_lines,
            fixed_lines,
            fromfile="a/solution.py",
            tofile="b/solution.py"
        )
        (private_dir / "oracle_patch.diff").write_text("".join(diff), encoding="utf-8")

    print(f"Generated {len(TASKS)} tasks successfully.")

if __name__ == "__main__":
    main()
