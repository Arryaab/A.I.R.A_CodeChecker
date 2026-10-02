"""
Track 1 (Tasks 001 - 020) Exact-Signature Comprehensive Research-Grade Oracle Definitions
"""

ORACLE_DATA_TRACK1 = {
    # -------------------------------------------------------------------------
    # Task 001: FastAPI Async Scope
    # -------------------------------------------------------------------------
    "task_001_fastapi_async_scope": {
        "test_code": '''import asyncio
import pytest
from solution import AsyncDependencyResolver

history = []

async def make_dep(name):
    global history
    try:
        yield f"val_{name}"
    finally:
        history.append(f"clean_{name}")

def test_oracle_happy_path_single_dependency():
    async def run():
        global history
        history = []
        resolver = AsyncDependencyResolver()
        val = await resolver.resolve(lambda: make_dep("X"))
        assert val == "val_X"
        await resolver.cleanup()
        assert history == ["clean_X"]
    asyncio.run(run())

def test_oracle_boundary_multiple_and_empty():
    async def run():
        resolver = AsyncDependencyResolver()
        await resolver.cleanup()
        assert resolver.cleanups == []
    asyncio.run(run())

def test_oracle_lifo_order_invariance():
    async def run():
        global history
        history = []
        resolver = AsyncDependencyResolver()
        a = await resolver.resolve(lambda: make_dep("A"))
        b = await resolver.resolve(lambda: make_dep("B"))
        c = await resolver.resolve(lambda: make_dep("C"))
        assert (a, b, c) == ("val_A", "val_B", "val_C")
        await resolver.cleanup()
        assert history == ["clean_C", "clean_B", "clean_A"]
    asyncio.run(run())

def test_oracle_idempotent_cleanup():
    async def run():
        global history
        history = []
        resolver = AsyncDependencyResolver()
        await resolver.resolve(lambda: make_dep("1"))
        await resolver.cleanup()
        assert history == ["clean_1"]
        assert len(resolver.cleanups) == 0
        await resolver.cleanup()
        assert history == ["clean_1"]
        assert len(resolver.cleanups) == 0
    asyncio.run(run())

def test_oracle_adversarial_shallow_fix():
    async def run():
        global history
        history = []
        resolver = AsyncDependencyResolver()
        for i in range(5):
            await resolver.resolve(lambda i=i: make_dep(str(i)))
        await resolver.cleanup()
        assert len(history) == 5
        assert history == [f"clean_{i}" for i in reversed(range(5))]
    asyncio.run(run())
''',
        "mutations": [
            {
                "id": "mutant_fifo_cleanup",
                "type": "ordering_inversion",
                "description": "Cleans up in FIFO order instead of LIFO order",
                "code": '''class AsyncDependencyResolver:
    def __init__(self):
        self.cleanups = []
    async def resolve(self, dep_func):
        gen = dep_func()
        val = await gen.__anext__()
        self.cleanups.append(gen)
        return val
    async def cleanup(self):
        for gen in self.cleanups:
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass
        self.cleanups.clear()
'''
            },
            {
                "id": "mutant_missing_clear",
                "type": "missing_cleanup",
                "description": "Fails to clear self.cleanups on cleanup completion",
                "code": '''class AsyncDependencyResolver:
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
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_sync_return_constant",
                "description": "Bypasses generator resolution and returns constant string",
                "code": '''class AsyncDependencyResolver:
    def __init__(self):
        self.cleanups = []
    async def resolve(self, dep_func):
        return "resource"
    async def cleanup(self):
        self.cleanups.clear()
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "standard",
            "TESTING_COMPLEXITY": "async_generator",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "async",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "AsyncDependencyResolver tracks resolved async generators and finalizes them in LIFO order upon cleanup(), idempotently clearing the registry."
    },

    # -------------------------------------------------------------------------
    # Task 002: FastAPI Middleware Exception
    # -------------------------------------------------------------------------
    "task_002_fastapi_middleware_exception": {
        "test_code": '''import pytest
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
''',
        "mutations": [
            {
                "id": "mutant_re_raise_exception",
                "type": "unhandled_exception",
                "description": "Re-raises CustomHTTPException instead of returning formatted response",
                "code": '''class CustomHTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

def execute_middleware_chain(handler, request):
    try:
        return handler(request)
    except Exception as exc:
        if isinstance(exc, CustomHTTPException):
            raise exc
        return {"status": 500, "error": "Internal Server Error"}
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_always_200",
                "description": "Always returns 200 success without checking exception type",
                "code": '''class CustomHTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

def execute_middleware_chain(handler, request):
    return {"status": 200, "data": "ok"}
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "exception_handling",
            "SECURITY_SENSITIVITY": "medium",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "execute_middleware_chain catches CustomHTTPException formatting it into a dict response with status and detail keys."
    },

    # -------------------------------------------------------------------------
    # Task 003: FastAPI Query Validation
    # -------------------------------------------------------------------------
    "task_003_fastapi_query_validation": {
        "test_code": '''import pytest
from solution import validate_query_param

def test_oracle_happy_path_exact_max_boundary():
    assert validate_query_param("a" * 50, min_length=1, max_length=50) is True

def test_oracle_boundary_min_length():
    assert validate_query_param("a", min_length=1, max_length=50) is True
    assert validate_query_param("", min_length=1, max_length=50) is False

def test_oracle_boundary_max_length_plus_one():
    assert validate_query_param("a" * 51, min_length=1, max_length=50) is False

def test_oracle_regex_pattern_matching():
    pat = r"^[a-z]+_\\d+$"
    assert validate_query_param("user_123", min_length=1, max_length=50, pattern=pat) is True
    assert validate_query_param("USER_123", min_length=1, max_length=50, pattern=pat) is False

def test_oracle_invariants_boolean_return():
    assert isinstance(validate_query_param("test"), bool)
''',
        "mutations": [
            {
                "id": "mutant_exclusive_max_boundary",
                "type": "wrong_boundary",
                "description": "Uses >= instead of > for max_length, rejecting boundary",
                "code": '''import re

def validate_query_param(val: str, min_length: int = 1, max_length: int = 50, pattern: str = None) -> bool:
    if len(val) < min_length:
        return False
    if len(val) >= max_length:
        return False
    if pattern and not re.match(pattern, val):
        return False
    return True
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_always_true",
                "description": "Always returns True without validation",
                "code": '''def validate_query_param(val: str, min_length: int = 1, max_length: int = 50, pattern: str = None) -> bool:
    return True
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "boundary_analysis",
            "SECURITY_SENSITIVITY": "medium",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Validates string query parameter bounds inclusively [min_length, max_length] and checks regular expression match when pattern is supplied."
    },

    # -------------------------------------------------------------------------
    # Task 004: FastAPI Header Encoding
    # -------------------------------------------------------------------------
    "task_004_fastapi_header_encoding": {
        "test_code": '''import pytest
from solution import decode_header

def test_oracle_happy_path_ascii():
    assert decode_header(b"Content-Type: application/json") == "Content-Type: application/json"

def test_oracle_happy_path_utf8_multibyte():
    val = "café".encode("utf-8")
    assert decode_header(val) == "café"

def test_oracle_boundary_empty_bytes():
    assert decode_header(b"") == ""

def test_oracle_negative_latin1_fallback():
    raw = b"hello \\xe9 world \\xff"
    res = decode_header(raw)
    assert res == raw.decode("latin-1")

def test_oracle_adversarial_do_not_default_to_latin1_first():
    val = "café".encode("utf-8")
    decoded = decode_header(val)
    assert len(decoded) == 4
    assert decoded == "café"
''',
        "mutations": [
            {
                "id": "mutant_unconditional_latin1",
                "type": "wrong_codec_order",
                "description": "Always decodes as latin-1 first, corrupting multi-byte UTF-8",
                "code": '''def decode_header(raw_bytes: bytes) -> str:
    return raw_bytes.decode('latin-1')
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_hardcode_string",
                "description": "Hardcodes decoded output",
                "code": '''def decode_header(raw_bytes: bytes) -> str:
    return "hello world"
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "encoding_fallback",
            "SECURITY_SENSITIVITY": "medium",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Header decoding prioritizes UTF-8 and safely falls back to Latin-1 on UnicodeDecodeError without data loss or exceptions."
    },

    # -------------------------------------------------------------------------
    # Task 005: FastAPI Lifespan State
    # -------------------------------------------------------------------------
    "task_005_fastapi_lifespan_state": {
        "test_code": '''import pytest
from solution import AppState

def test_oracle_happy_path_set_get():
    state = AppState()
    state.set("port", 8000)
    assert state.get("port") == 8000

def test_oracle_boundary_missing_key():
    state = AppState()
    assert state.get("nonexistent") is None
    assert state.get("nonexistent", "default") == "default"

def test_oracle_regression_identity_preservation():
    state = AppState()
    external_ref = state._state
    state.set("key1", "val1")
    state.clear()
    assert state._state is external_ref
    assert len(external_ref) == 0

def test_oracle_interaction_repopulation():
    state = AppState()
    alias = state._state
    state.set("a", 1)
    state.clear()
    state.set("b", 2)
    assert alias.get("b") == 2
    assert "a" not in alias
''',
        "mutations": [
            {
                "id": "mutant_reassign_dict",
                "type": "reference_break",
                "description": "Reassigns _state to a new empty dict breaking existing references",
                "code": '''class AppState:
    def __init__(self):
        self._state = {}
    def set(self, key, value):
        self._state[key] = value
    def get(self, key, default=None):
        return self._state.get(key, default)
    def clear(self):
        self._state = {}
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_noop_clear",
                "description": "Does nothing on clear",
                "code": '''class AppState:
    def __init__(self):
        self._state = {}
    def set(self, key, value):
        self._state[key] = value
    def get(self, key, default=None):
        return self._state.get(key, default)
    def clear(self):
        pass
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "object_identity",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "AppState maintains dictionary identity across clear() operations by mutating in place."
    },

    # -------------------------------------------------------------------------
    # Task 006: Pydantic Root Validator
    # -------------------------------------------------------------------------
    "task_006_pydantic_root_validator": {
        "test_code": '''import pytest
from solution import validate_user_payload

def test_oracle_happy_path_combine_and_preserve():
    payload = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "role": "mathematician",
        "id": 42
    }
    result = validate_user_payload(payload)
    assert result["full_name"] == "Ada Lovelace"
    assert result["first_name"] == "Ada"
    assert result["last_name"] == "Lovelace"
    assert result["email"] == "ada@example.com"
    assert result["role"] == "mathematician"
    assert result["id"] == 42

def test_oracle_boundary_only_first_name():
    payload = {"first_name": "Ada", "email": "ada@example.com"}
    result = validate_user_payload(payload)
    assert "full_name" not in result
    assert result["first_name"] == "Ada"

def test_oracle_boundary_neither_name():
    payload = {"role": "guest", "id": 10}
    assert validate_user_payload(payload) == {"role": "guest", "id": 10}

def test_oracle_regression_input_immutability():
    original = {"first_name": "Alan", "last_name": "Turing", "dept": "CS"}
    result = validate_user_payload(original)
    assert result["dept"] == "CS"
    assert result["full_name"] == "Alan Turing"
''',
        "mutations": [
            {
                "id": "mutant_omit_original_fields",
                "type": "data_loss",
                "description": "Returns dictionary with full_name only, omitting original fields",
                "code": '''def validate_user_payload(data: dict) -> dict:
    if "first_name" in data and "last_name" in data:
        return {"full_name": f"{data['first_name']} {data['last_name']}"}
    return data
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_hardcode_name",
                "description": "Hardcodes John Doe",
                "code": '''def validate_user_payload(data: dict) -> dict:
    res = dict(data)
    res["full_name"] = "John Doe"
    return res
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "schema_preservation",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Constructs full_name when both first and last name keys exist while retaining all preexisting dictionary fields."
    },

    # -------------------------------------------------------------------------
    # Task 007: Pydantic Recursive Model
    # -------------------------------------------------------------------------
    "task_007_pydantic_recursive_model": {
        "test_code": '''import pytest
from solution import TreeNode, serialize_tree

def test_oracle_happy_path_acyclic_tree():
    leaf1 = TreeNode(1)
    leaf2 = TreeNode(2)
    root = TreeNode(10, [leaf1, leaf2])
    res = serialize_tree(root)
    assert res["value"] == 10
    assert len(res["children"]) == 2
    assert res["children"][0]["value"] == 1
    assert res["children"][1]["value"] == 2

def test_oracle_boundary_single_node():
    node = TreeNode(42)
    res = serialize_tree(node)
    assert res == {"value": 42, "children": []}

def test_oracle_negative_cyclic_reference():
    n1 = TreeNode(10)
    n2 = TreeNode(20, [n1])
    n1.children.append(n2)
    res = serialize_tree(n1)
    assert res["value"] == 10
    assert res["children"][0]["children"][0]["ref"] is True

def test_oracle_regression_self_loop():
    loop_node = TreeNode(99)
    loop_node.children.append(loop_node)
    res = serialize_tree(loop_node)
    assert res["value"] == 99
    assert res["children"][0]["ref"] is True
''',
        "mutations": [
            {
                "id": "mutant_omit_seen_tracking",
                "type": "infinite_recursion",
                "description": "Fails to pass seen set down recursive calls",
                "code": '''class TreeNode:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []

def serialize_tree(node: TreeNode, seen=None):
    return {
        "value": node.value,
        "children": [serialize_tree(c) for c in node.children]
    }
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_truncate_depth_one",
                "description": "Always returns empty children",
                "code": '''class TreeNode:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []

def serialize_tree(node: TreeNode, seen=None):
    return {"value": node.value, "children": []}
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(V + E)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "graph_traversal",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Serializes recursive tree structures safely handling cycles by tracking visited node object identities and marking back-references with {'ref': True}."
    },

    # -------------------------------------------------------------------------
    # Task 008: Pydantic Discriminator Union
    # -------------------------------------------------------------------------
    "task_008_pydantic_discriminator_union": {
        "test_code": '''import pytest
from solution import parse_event

def test_oracle_happy_path_click_event():
    res = parse_event({"type": "click", "x": 10, "y": 20})
    assert res == {"kind": "click", "x": 10, "y": 20}

def test_oracle_happy_path_hover_event():
    res = parse_event({"type": "hover", "duration": 5.5})
    assert res == {"kind": "hover", "duration": 5.5}

def test_oracle_negative_missing_type_raises():
    with pytest.raises(ValueError, match="Missing discriminator 'type'"):
        parse_event({"x": 10})

def test_oracle_negative_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown event type"):
        parse_event({"type": "scroll"})

def test_oracle_negative_non_dict_raises():
    with pytest.raises(ValueError):
        parse_event("not_a_dict")
''',
        "mutations": [
            {
                "id": "mutant_accept_unknown_events",
                "type": "validation_bypass",
                "description": "Accepts unknown event types without raising ValueError",
                "code": '''def parse_event(data: dict):
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError("Missing discriminator 'type'")
    return data
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_hardcode_click",
                "description": "Hardcodes click event return",
                "code": '''def parse_event(data: dict):
    return {"kind": "click", "x": 0, "y": 0}
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "schema_validation",
            "SECURITY_SENSITIVITY": "medium",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Parses event payloads using the type discriminator, dispatching click and hover events and raising ValueError on missing or unknown types."
    },

    # -------------------------------------------------------------------------
    # Task 009: Pydantic Custom Serializer
    # -------------------------------------------------------------------------
    "task_009_pydantic_custom_serializer": {
        "test_code": '''import pytest
from datetime import datetime
from decimal import Decimal
from solution import custom_serializer

def test_oracle_happy_path_decimal():
    res = custom_serializer(Decimal("19.99"))
    assert res == 19.99
    assert isinstance(res, float)

def test_oracle_happy_path_datetime():
    dt = datetime(2026, 9, 27, 10, 0, 0)
    assert custom_serializer(dt) == dt.isoformat()

def test_oracle_regression_primitives_unchanged():
    assert custom_serializer(100) == 100
    assert custom_serializer("hello") == "hello"
    assert custom_serializer(True) is True
    assert custom_serializer(None) is None

def test_oracle_fallback_to_str():
    class CustomObj:
        def __str__(self):
            return "custom_str"
    assert custom_serializer(CustomObj()) == "custom_str"
''',
        "mutations": [
            {
                "id": "mutant_decimal_as_str",
                "type": "wrong_type",
                "description": "Converts Decimal to str instead of float",
                "code": '''from datetime import datetime
from decimal import Decimal

def custom_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    return str(obj)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_str_everything",
                "description": "Stringifies everything",
                "code": '''def custom_serializer(obj):
    return str(obj)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "type_dispatch",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Serializes Decimal to float and datetime to ISO format while passing primitives through."
    },

    # -------------------------------------------------------------------------
    # Task 010: Pydantic Generic Model
    # -------------------------------------------------------------------------
    "task_010_pydantic_generic_model": {
        "test_code": '''import pytest
from solution import GenericEnvelope

def test_oracle_happy_path_valid_int_items():
    env = GenericEnvelope(int)
    res = env.parse({"items": [1, 2, 3]})
    assert res == {"count": 3, "items": [1, 2, 3]}

def test_oracle_boundary_empty_items():
    env = GenericEnvelope(str)
    res = env.parse({"items": []})
    assert res == {"count": 0, "items": []}

def test_oracle_negative_invalid_type_raises():
    env = GenericEnvelope(int)
    with pytest.raises(TypeError, match="is not of type int"):
        env.parse({"items": [1, "two", 3]})

def test_oracle_negative_empty_payload():
    env = GenericEnvelope(str)
    res = env.parse({})
    assert res == {"count": 0, "items": []}
''',
        "mutations": [
            {
                "id": "mutant_omit_type_check",
                "type": "validation_missing",
                "description": "Fails to validate item types",
                "code": '''class GenericEnvelope:
    def __init__(self, item_cls):
        self.item_cls = item_cls
    def parse(self, payload: dict):
        items = payload.get("items", [])
        return {"count": len(items), "items": items}
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_empty_items",
                "description": "Always returns empty items",
                "code": '''class GenericEnvelope:
    def __init__(self, item_cls):
        self.item_cls = item_cls
    def parse(self, payload: dict):
        return {"count": 0, "items": []}
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "type_checking",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "GenericEnvelope parses payloads verifying every element in items conforms to item_cls, raising TypeError otherwise."
    },

    # -------------------------------------------------------------------------
    # Task 011: Click Subcommand Param
    # -------------------------------------------------------------------------
    "task_011_click_subcommand_param": {
        "test_code": '''import pytest
from solution import CLIContext, CommandGroup

def test_oracle_happy_path_context_passed():
    grp = CommandGroup()
    grp.add("status", lambda ctx: f"verbose={ctx.verbose}")
    ctx = CLIContext(verbose=True)
    assert grp.invoke(ctx, "status") == "verbose=True"

def test_oracle_happy_path_with_extra_args():
    grp = CommandGroup()
    grp.add("echo", lambda ctx, msg: f"[{ctx.verbose}] {msg}")
    ctx = CLIContext(verbose=False)
    assert grp.invoke(ctx, "echo", "hello") == "[False] hello"

def test_oracle_negative_unknown_subcommand_raises():
    grp = CommandGroup()
    ctx = CLIContext()
    with pytest.raises(ValueError, match="Unknown command nonexistent"):
        grp.invoke(ctx, "nonexistent")
''',
        "mutations": [
            {
                "id": "mutant_omit_ctx_argument",
                "type": "wrong_call_signature",
                "description": "Invokes handler without passing ctx",
                "code": '''class CLIContext:
    def __init__(self, verbose=False):
        self.verbose = verbose

class CommandGroup:
    def __init__(self):
        self.subcommands = {}
    def add(self, name, handler):
        self.subcommands[name] = handler
    def invoke(self, ctx: CLIContext, cmd_name: str, *args):
        if cmd_name in self.subcommands:
            return self.subcommands[cmd_name](*args)
        raise ValueError(f"Unknown command {cmd_name}")
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_pass_none",
                "description": "Passes None instead of ctx",
                "code": '''class CLIContext:
    def __init__(self, verbose=False):
        self.verbose = verbose

class CommandGroup:
    def __init__(self):
        self.subcommands = {}
    def add(self, name, handler):
        self.subcommands[name] = handler
    def invoke(self, ctx: CLIContext, cmd_name: str, *args):
        if cmd_name in self.subcommands:
            return self.subcommands[cmd_name](None, *args)
        raise ValueError(f"Unknown command {cmd_name}")
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "call_dispatch",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "CommandGroup invokes subcommands passing CLIContext instance as the first argument."
    },

    # -------------------------------------------------------------------------
    # Task 012: Click Context Leak
    # -------------------------------------------------------------------------
    "task_012_click_context_leak": {
        "test_code": '''import pytest
from solution import Context

def test_oracle_happy_path_child_copies_data():
    parent = Context({"env": "prod"})
    child = parent.child()
    assert child.data == {"env": "prod"}
    assert child.data is not parent.data

def test_oracle_negative_child_mutation_isolated():
    parent = Context({"env": "prod"})
    child = parent.child()
    child.data["env"] = "staging"
    child.data["new"] = 123
    assert parent.data["env"] == "prod"
    assert "new" not in parent.data

def test_oracle_boundary_empty_parent():
    parent = Context()
    child = parent.child()
    child.data["k"] = "v"
    assert len(parent.data) == 0
''',
        "mutations": [
            {
                "id": "mutant_shared_reference",
                "type": "reference_leak",
                "description": "Passes self.data reference without copying",
                "code": '''class Context:
    def __init__(self, data=None):
        self.data = data if data is not None else {}
    def child(self):
        return Context(self.data)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_empty_child",
                "description": "Always returns child with empty data",
                "code": '''class Context:
    def __init__(self, data=None):
        self.data = data or {}
    def child(self):
        return Context({})
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "state_isolation",
            "SECURITY_SENSITIVITY": "medium",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Context.child() performs a shallow copy of context data ensuring child mutations never leak to parent."
    },

    # -------------------------------------------------------------------------
    # Task 013: Click Custom Param Type
    # -------------------------------------------------------------------------
    "task_013_click_custom_param_type": {
        "test_code": '''import pytest
from solution import parse_int_range

def test_oracle_happy_path_endpoints():
    assert parse_int_range("10", 10, 20) == 10
    assert parse_int_range("20", 10, 20) == 20
    assert parse_int_range("15", 10, 20) == 15

def test_oracle_negative_strictly_below():
    with pytest.raises(ValueError, match="out of range"):
        parse_int_range("9", 10, 20)

def test_oracle_negative_strictly_above():
    with pytest.raises(ValueError, match="out of range"):
        parse_int_range("21", 10, 20)

def test_oracle_boundary_negative_numbers():
    assert parse_int_range("-5", -10, -5) == -5
    with pytest.raises(ValueError):
        parse_int_range("-4", -10, -5)
''',
        "mutations": [
            {
                "id": "mutant_exclusive_lower_bound",
                "type": "wrong_boundary",
                "description": "Rejects lower endpoint using <=",
                "code": '''def parse_int_range(val_str: str, min_val: int, max_val: int) -> int:
    val = int(val_str)
    if val <= min_val or val > max_val:
        raise ValueError(f"Value {val} out of range [{min_val}, {max_val}]")
    return val
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_return_min",
                "description": "Always returns min_val",
                "code": '''def parse_int_range(val_str: str, min_val: int, max_val: int) -> int:
    return min_val
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "boundary_analysis",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Parses integer range parameter string ensuring integer value is inclusively within [min_val, max_val]."
    },

    # -------------------------------------------------------------------------
    # Task 014: Click Choice Case Sensitive
    # -------------------------------------------------------------------------
    "task_014_click_choice_case_sensitive": {
        "test_code": '''import pytest
from solution import match_choice

def test_oracle_happy_path_case_insensitive():
    choices = ["Fast", "Standard", "Deep"]
    assert match_choice("fast", choices, case_sensitive=False) == "Fast"
    assert match_choice("STANDARD", choices, case_sensitive=False) == "Standard"

def test_oracle_happy_path_case_sensitive():
    choices = ["Fast", "fast"]
    assert match_choice("Fast", choices, case_sensitive=True) == "Fast"
    assert match_choice("fast", choices, case_sensitive=True) == "fast"

def test_oracle_negative_case_sensitive_mismatch():
    choices = ["Fast", "Deep"]
    with pytest.raises(ValueError):
        match_choice("fast", choices, case_sensitive=True)

def test_oracle_negative_invalid_choice():
    with pytest.raises(ValueError):
        match_choice("unknown", ["A", "B"], case_sensitive=False)
''',
        "mutations": [
            {
                "id": "mutant_ignore_case_sensitive_flag",
                "type": "flag_ignored",
                "description": "Always performs case-sensitive match",
                "code": '''def match_choice(val: str, choices: list[str], case_sensitive: bool = True) -> str:
    if val in choices:
        return val
    raise ValueError(f"'{val}' is not in {choices}")
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_return_first",
                "description": "Returns choices[0]",
                "code": '''def match_choice(val: str, choices: list[str], case_sensitive: bool = True) -> str:
    return choices[0]
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "case_matching",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Matches choice option normalizing case-insensitively when case_sensitive=False and raising ValueError on unknown choices."
    },

    # -------------------------------------------------------------------------
    # Task 015: aiohttp Session Reuse
    # -------------------------------------------------------------------------
    "task_015_aiohttp_session_reuse": {
        "test_code": '''import pytest
from solution import ConnectionPool

def test_oracle_happy_path_acquire_release():
    pool = ConnectionPool(size=3)
    conn = pool.acquire()
    assert conn == "conn"
    assert pool.available == 2
    pool.release()
    assert pool.available == 3

def test_oracle_negative_double_release_capped():
    pool = ConnectionPool(size=2)
    pool.acquire()
    pool.release()
    pool.release()
    pool.release()
    assert pool.available == 2

def test_oracle_negative_exhausted_pool():
    pool = ConnectionPool(size=1)
    pool.acquire()
    with pytest.raises(RuntimeError, match="Pool exhausted"):
        pool.acquire()
''',
        "mutations": [
            {
                "id": "mutant_no_upper_bound_on_release",
                "type": "overflow_defect",
                "description": "Increments available unconditionally without checking size",
                "code": '''class ConnectionPool:
    def __init__(self, size=10):
        self.available = size
        self.size = size
    def acquire(self):
        if self.available <= 0:
            raise RuntimeError("Pool exhausted")
        self.available -= 1
        return "conn"
    def release(self):
        self.available += 1
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_set_available_constant",
                "description": "Sets available to fixed size",
                "code": '''class ConnectionPool:
    def __init__(self, size=10):
        self.available = size
        self.size = size
    def acquire(self):
        return "conn"
    def release(self):
        self.available = self.size
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "resource_accounting",
            "SECURITY_SENSITIVITY": "medium",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "ConnectionPool ensures release() never increases available count beyond max capacity."
    },

    # -------------------------------------------------------------------------
    # Task 016: aiohttp Chunk Timeout
    # -------------------------------------------------------------------------
    "task_016_aiohttp_chunk_timeout": {
        "test_code": '''import pytest
from solution import ChunkStreamReader

def test_oracle_happy_path_all_chunks():
    chunks = [(b"alpha", 0.1), (b"beta", 0.2)]
    reader = ChunkStreamReader(chunks)
    assert reader.read_all(time_limit=1.0) == b"alphabeta"

def test_oracle_negative_timeout_excludes_late_chunk():
    chunks = [(b"ok1", 0.3), (b"late_chunk", 1.0)]
    reader = ChunkStreamReader(chunks)
    with pytest.raises(TimeoutError, match="Read timeout exceeded"):
        reader.read_all(time_limit=0.5)
    assert reader.buffer == [b"ok1"]

def test_oracle_regression_first_chunk_timeout():
    chunks = [(b"too_late", 2.0)]
    reader = ChunkStreamReader(chunks)
    with pytest.raises(TimeoutError):
        reader.read_all(time_limit=1.0)
    assert reader.buffer == []
''',
        "mutations": [
            {
                "id": "mutant_append_before_check",
                "type": "premature_mutation",
                "description": "Appends late chunk to buffer before checking timeout threshold",
                "code": '''class ChunkStreamReader:
    def __init__(self, chunks, timeout_s=1.0):
        self.chunks = chunks
        self.timeout_s = timeout_s
        self.buffer = []
    def read_all(self, time_limit: float):
        self.buffer = []
        total_time = 0.0
        for data, delay in self.chunks:
            total_time += delay
            self.buffer.append(data)
            if total_time > time_limit:
                raise TimeoutError("Read timeout exceeded")
        return b"".join(self.buffer)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_empty_buffer",
                "description": "Always returns empty bytes",
                "code": '''class ChunkStreamReader:
    def __init__(self, chunks, timeout_s=1.0):
        self.chunks = chunks
        self.timeout_s = timeout_s
        self.buffer = []
    def read_all(self, time_limit: float):
        return b""
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "timing_and_buffer",
            "SECURITY_SENSITIVITY": "medium",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "ChunkStreamReader checks timeout before accumulating chunks, raising TimeoutError and omitting late chunks."
    },

    # -------------------------------------------------------------------------
    # Task 017: aiohttp Cookie Jar Domain
    # -------------------------------------------------------------------------
    "task_017_aiohttp_cookie_jar_domain": {
        "test_code": '''import pytest
from solution import is_domain_match

def test_oracle_happy_path_exact():
    assert is_domain_match("example.com", "example.com") is True
    assert is_domain_match("EXAMPLE.COM", "example.com") is True

def test_oracle_happy_path_subdomain():
    assert is_domain_match("api.example.com", "example.com") is True
    assert is_domain_match("sub.domain.example.com", "example.com") is True
    assert is_domain_match("api.example.com", ".example.com") is True

def test_oracle_negative_suffix_spoofing():
    # Security: attackerexample.com MUST NOT match example.com
    assert is_domain_match("notexample.com", "example.com") is False
    assert is_domain_match("attackerexample.com", "example.com") is False
    assert is_domain_match("fakeexample.com", ".example.com") is False
''',
        "mutations": [
            {
                "id": "mutant_naive_endswith",
                "type": "security_flaw",
                "description": "Uses naive endswith permitting suffix spoofing attacks",
                "code": '''def is_domain_match(request_domain: str, cookie_domain: str) -> bool:
    return request_domain.endswith(cookie_domain)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_exact_match_only",
                "description": "Only supports exact match, breaking legitimate subdomains",
                "code": '''def is_domain_match(request_domain: str, cookie_domain: str) -> bool:
    return request_domain.lower() == cookie_domain.lower().lstrip(".")
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "security_boundary",
            "SECURITY_SENSITIVITY": "high",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Validates exact and subdomain cookie matches while preventing suffix spoofing."
    },

    # -------------------------------------------------------------------------
    # Task 018: Crypto PKCS#7 Padding
    # -------------------------------------------------------------------------
    "task_018_crypto_pkcs7_padding": {
        "test_code": '''import pytest
from solution import pkcs7_unpad

def test_oracle_happy_path_valid():
    data = b"message" + b"\\x09" * 9
    assert pkcs7_unpad(data, block_size=16) == b"message"

def test_oracle_boundary_full_block_padding():
    data = b"1234567890123456" + b"\\x10" * 16
    assert pkcs7_unpad(data, block_size=16) == b"1234567890123456"

def test_oracle_negative_corrupt_padding_byte():
    corrupt = b"message" + b"\\x00" * 7 + b"\\x02\\x03"
    with pytest.raises(ValueError):
        pkcs7_unpad(corrupt, block_size=16)

def test_oracle_negative_invalid_block_length():
    with pytest.raises(ValueError, match="Invalid block length"):
        pkcs7_unpad(b"short", block_size=16)
''',
        "mutations": [
            {
                "id": "mutant_check_last_byte_only",
                "type": "security_flaw",
                "description": "Checks only the final byte without verifying all padding bytes",
                "code": '''def pkcs7_unpad(data: bytes, block_size: int = 16) -> bytes:
    if not data or len(data) % block_size != 0:
        raise ValueError("Invalid block length")
    pad_len = data[-1]
    if pad_len == 0 or pad_len > block_size:
        raise ValueError("Invalid padding value")
    return data[:-pad_len]
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_strip_one_byte",
                "description": "Always strips 1 byte",
                "code": '''def pkcs7_unpad(data: bytes, block_size: int = 16) -> bytes:
    return data[:-1]
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "cryptographic_integrity",
            "SECURITY_SENSITIVITY": "high",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Unpads PKCS#7 encoded byte strings verifying all pad_len trailing bytes equal pad_len."
    },

    # -------------------------------------------------------------------------
    # Task 019: Crypto ASN.1 Length Bounds
    # -------------------------------------------------------------------------
    "task_019_crypto_asn1_length_bounds": {
        "test_code": '''import pytest
from solution import parse_asn1_length

def test_oracle_happy_path_short_form():
    length, next_offset = parse_asn1_length(bytes([0x2A, 0x01]), offset=0)
    assert length == 42
    assert next_offset == 1

def test_oracle_happy_path_long_form():
    data = bytes([0x82, 0x01, 0x00, 0xAA])
    length, next_offset = parse_asn1_length(data, offset=0)
    assert length == 256
    assert next_offset == 3

def test_oracle_negative_truncated_length():
    with pytest.raises(ValueError, match="Truncated ASN.1 length header"):
        parse_asn1_length(bytes([0x82, 0x01]), offset=0)

def test_oracle_negative_eof():
    with pytest.raises(ValueError, match="Unexpected EOF"):
        parse_asn1_length(b"", offset=0)
''',
        "mutations": [
            {
                "id": "mutant_omit_bounds_check",
                "type": "buffer_overrun",
                "description": "Fails to check if offset + 1 + num_octets exceeds buffer length",
                "code": '''def parse_asn1_length(data: bytes, offset: int = 0) -> tuple[int, int]:
    if offset >= len(data):
        raise ValueError("Unexpected EOF reading length")
    first = data[offset]
    if first < 0x80:
        return first, offset + 1
    num_octets = first & 0x7F
    if num_octets == 0 or num_octets > 4:
        raise ValueError("Invalid length octet count")
    length = int.from_bytes(data[offset + 1:offset + 1 + num_octets], "big")
    return length, offset + 1 + num_octets
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_short_form_only",
                "description": "Only supports short form length",
                "code": '''def parse_asn1_length(data: bytes, offset: int = 0) -> tuple[int, int]:
    return data[offset], offset + 1
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "binary_parsing",
            "SECURITY_SENSITIVITY": "high",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Parses ASN.1 DER length octets with strict bounds checking, raising ValueError on EOF or truncated headers."
    },

    # -------------------------------------------------------------------------
    # Task 020: Crypto Constant Time Compare
    # -------------------------------------------------------------------------
    "task_020_crypto_constant_time_compare": {
        "test_code": '''import pytest
from solution import constant_time_compare

def test_oracle_happy_path_equal():
    assert constant_time_compare(b"hash123", b"hash123") is True

def test_oracle_negative_same_first_byte_diff_remainder():
    # Both start with 'h' and have same length; buggy returns True
    assert constant_time_compare(b"hash123", b"hash456") is False

def test_oracle_negative_differ_last_byte():
    assert constant_time_compare(b"key_a", b"key_b") is False

def test_oracle_negative_different_lengths():
    assert constant_time_compare(b"short", b"longer_string") is False

def test_oracle_boundary_empty_bytes():
    assert constant_time_compare(b"", b"") is True
    assert constant_time_compare(b"", b"a") is False
''',
        "mutations": [
            {
                "id": "mutant_first_byte_only",
                "type": "security_flaw",
                "description": "Compares only length and first byte",
                "code": '''def constant_time_compare(val1: bytes, val2: bytes) -> bool:
    if len(val1) != len(val2):
        return False
    return len(val1) == len(val2) and (val1[0] == val2[0] if val1 else True)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_equality_only",
                "description": "Returns length equality only",
                "code": '''def constant_time_compare(val1: bytes, val2: bytes) -> bool:
    return len(val1) == len(val2)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "cryptographic_timing",
            "SECURITY_SENSITIVITY": "high",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Performs constant-time byte string comparison accumulating differences via bitwise OR."
    }
}
