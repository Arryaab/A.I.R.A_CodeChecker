"""
AegisBench v2 MLVerify Expansion: Category C Task Definitions
Focus: Security Defects (Tasks 063 - 068)
"""

TASKS_CAT_C = [
    {
        "id": "task_063_path_traversal_archive_extract",
        "category": "security_defect",
        "difficulty": "medium",
        "desc": "Prevent Zip Slip / Path Traversal vulnerability when extracting archive file paths",
        "expected": "Validates resolved destination path is strictly within target directory; raises ValueError otherwise",
        "tags": ["security", "path-traversal", "zip-slip"],
        "repo": "https://github.com/aegis-benchmark/archive-tools",
        "commit": "6708091011121314151617181920212223242526",
        "buggy_code": '''import os
from pathlib import Path

def resolve_safe_extract_path(dest_dir: str, member_filename: str) -> str:
    """Calculates extraction path ensuring no breakout from dest_dir."""
    # BUG: Simply joins paths without verifying whether resolved path is inside dest_dir
    dest_path = os.path.abspath(dest_dir)
    target = os.path.join(dest_path, member_filename)
    return target
''',
        "fixed_code": '''import os
from pathlib import Path

def resolve_safe_extract_path(dest_dir: str, member_filename: str) -> str:
    """Calculates extraction path ensuring no breakout from dest_dir."""
    dest_path = os.path.abspath(dest_dir)
    # Resolve target path and verify prefix containment
    target = os.path.abspath(os.path.join(dest_path, member_filename))
    if not (target == dest_path or target.startswith(dest_path + os.sep)):
        raise ValueError(f"Path traversal detected: {member_filename} attempts to escape {dest_dir}")
    return target
''',
        "test_code": '''import os
import pytest
from solution import resolve_safe_extract_path

def test_safe_relative_path():
    path = resolve_safe_extract_path("/tmp/extract", "docs/readme.txt")
    assert path.endswith("docs" + os.sep + "readme.txt")
''',
        "hidden_test_code": '''import pytest
from solution import resolve_safe_extract_path

def test_relative_escape_raises():
    with pytest.raises(ValueError):
        resolve_safe_extract_path("/tmp/extract", "../../../etc/passwd")

def test_nested_parent_traversal():
    with pytest.raises(ValueError):
        resolve_safe_extract_path("/tmp/extract", "sub/../../escape.txt")
''',
        "oracle_test_code": '''import pytest
from solution import resolve_safe_extract_path

def test_oracle_traversal_variations():
    cases = ["../evil.sh", "..\\\\evil.bat", "/etc/shadow", "foo/bar/../../../../secret"]
    for c in cases:
        try:
            res = resolve_safe_extract_path("/tmp/safe", c)
            # If it didn't raise, ensure it did not escape
            import os
            assert res.startswith(os.path.abspath("/tmp/safe") + os.sep)
        except ValueError:
            pass
''',
        "behavioral_spec": "Path extraction resolver must strictly prevent filesystem breakout via parent traversal tokens."
    },
    {
        "id": "task_064_ssrf_url_scheme_validation",
        "category": "security_defect",
        "difficulty": "hard",
        "desc": "Harden outgoing URL validator against SSRF and non-HTTP protocol schemes",
        "expected": "Only allows http/https schemes and rejects loopback, link-local, and private IP addresses",
        "tags": ["security", "ssrf", "url-validation"],
        "repo": "https://github.com/aegis-benchmark/webhook-dispatcher",
        "commit": "7809101112131415161718192021222324252627",
        "buggy_code": '''from urllib.parse import urlparse

def is_safe_webhook_url(url: str) -> bool:
    """Validates whether a URL is safe for outgoing webhook dispatch."""
    parsed = urlparse(url)
    # BUG: Fails to enforce http/https scheme and only checks trivial string match for 127.0.0.1
    host = parsed.hostname or ""
    if host.lower() in ("localhost", "127.0.0.1"):
        return False
    return True
''',
        "fixed_code": '''from urllib.parse import urlparse
import ipaddress

def is_safe_webhook_url(url: str) -> bool:
    """Validates whether a URL is safe for outgoing webhook dispatch."""
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        return False
    host = (parsed.hostname or "").strip()
    if not host:
        return False
    if host.lower() == "localhost":
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass
    return True
''',
        "test_code": '''import pytest
from solution import is_safe_webhook_url

def test_safe_public_url():
    assert is_safe_webhook_url("https://api.example.com/webhook") is True

def test_obvious_localhost_rejected():
    assert is_safe_webhook_url("http://localhost:8080/hook") is False
''',
        "hidden_test_code": '''import pytest
from solution import is_safe_webhook_url

def test_dangerous_schemes_rejected():
    assert is_safe_webhook_url("file:///etc/passwd") is False
    assert is_safe_webhook_url("gopher://127.0.0.1:70") is False

def test_private_subnets_rejected():
    assert is_safe_webhook_url("http://192.168.1.1/admin") is False
    assert is_safe_webhook_url("http://10.0.0.1/") is False
    assert is_safe_webhook_url("http://169.254.169.254/latest/meta-data") is False
''',
        "oracle_test_code": '''import pytest
from solution import is_safe_webhook_url

def test_oracle_ssrf_corpus():
    bad = [
        "http://127.0.0.1/", "http://[::1]/", "file:///bin/sh",
        "http://10.255.255.1/", "ftp://example.com"
    ]
    for u in bad:
        assert is_safe_webhook_url(u) is False
''',
        "behavioral_spec": "Webhook validator must restrict schemes to http/https and reject private IP spaces."
    },
    {
        "id": "task_065_yaml_unsafe_constructor_load",
        "category": "security_defect",
        "difficulty": "medium",
        "desc": "Restrict dynamic object instantiation in YAML config deserializer to explicit allowlist",
        "expected": "Only instantiates classes present in ALLOWED_TYPES; raises SecurityError otherwise",
        "tags": ["security", "deserialization", "allowlist"],
        "repo": "https://github.com/aegis-benchmark/config-loader",
        "commit": "8901020304050607080910111213141516171819",
        "buggy_code": '''class SecurityError(Exception):
    pass

class UserProfile:
    def __init__(self, name: str):
        self.name = name

ALLOWED_TYPES = {"UserProfile": UserProfile}

def instantiate_custom_type(type_name: str, kwargs: dict):
    # BUG: Directly accesses globals() allowing instantiation of arbitrary classes
    if type_name in globals():
        cls = globals()[type_name]
        return cls(**kwargs)
    raise ValueError(f"Unknown type: {type_name}")
''',
        "fixed_code": '''class SecurityError(Exception):
    pass

class UserProfile:
    def __init__(self, name: str):
        self.name = name

ALLOWED_TYPES = {"UserProfile": UserProfile}

def instantiate_custom_type(type_name: str, kwargs: dict):
    if type_name not in ALLOWED_TYPES:
        raise SecurityError(f"Prohibited type instantiation: {type_name} is not in safe allowlist")
    cls = ALLOWED_TYPES[type_name]
    return cls(**kwargs)
''',
        "test_code": '''import pytest
from solution import instantiate_custom_type, UserProfile

def test_allowed_type():
    obj = instantiate_custom_type("UserProfile", {"name": "Alice"})
    assert isinstance(obj, UserProfile)
    assert obj.name == "Alice"
''',
        "hidden_test_code": '''import pytest
from solution import instantiate_custom_type, SecurityError

def test_unregistered_type_blocked():
    with pytest.raises(SecurityError):
        instantiate_custom_type("SecurityError", {"args": ("test",)})

def test_arbitrary_callable_blocked():
    with pytest.raises(SecurityError):
        instantiate_custom_type("eval", {})
''',
        "oracle_test_code": '''import pytest
from solution import instantiate_custom_type, SecurityError

def test_oracle_allowlist_enforcement():
    for dangerous in ["object", "dict", "list", "Exception", "bytearray"]:
        with pytest.raises(SecurityError):
            instantiate_custom_type(dangerous, {})
''',
        "behavioral_spec": "Dynamic deserializer must restrict constructors strictly to the predefined allowlist."
    },
    {
        "id": "task_066_sql_identifier_sanitization",
        "category": "security_defect",
        "difficulty": "medium",
        "desc": "Safely quote and escape dynamic SQL identifiers (table and column names)",
        "expected": "Encloses in double quotes and escapes internal double quotes by doubling them ('\"\"')",
        "tags": ["sql", "sanitization", "injection"],
        "repo": "https://github.com/aegis-benchmark/sql-builder",
        "commit": "9001020304050607080910111213141516171819",
        "buggy_code": '''def quote_identifier(identifier: str) -> str:
    """Quotes a SQL identifier according to ANSI SQL standards."""
    if not identifier:
        raise ValueError("Identifier cannot be empty")
    # BUG: Wraps in quotes but fails to escape internal double quotes, permitting injection breakout
    return f'"{identifier}"'
''',
        "fixed_code": '''def quote_identifier(identifier: str) -> str:
    """Quotes a SQL identifier according to ANSI SQL standards."""
    if not identifier:
        raise ValueError("Identifier cannot be empty")
    if "\\x00" in identifier:
        raise ValueError("Identifier cannot contain null bytes")
    # ANSI SQL: escape double quotes by doubling them
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'
''',
        "test_code": '''import pytest
from solution import quote_identifier

def test_standard_identifier():
    assert quote_identifier("users") == '"users"'
    assert quote_identifier("first_name") == '"first_name"'
''',
        "hidden_test_code": '''import pytest
from solution import quote_identifier

def test_embedded_quotes_escaped():
    assert quote_identifier('user"name') == '"user""name"'
    assert quote_identifier('evil"; DROP TABLE users; --') == '"evil""; DROP TABLE users; --"'

def test_null_byte_rejected():
    with pytest.raises(ValueError):
        quote_identifier("users\\x00evil")
''',
        "oracle_test_code": '''import pytest
from solution import quote_identifier

def test_oracle_quote_invariants():
    for name in ['col', 'a"b', 'a""b', 'test--1']:
        q = quote_identifier(name)
        assert q.startswith('"') and q.endswith('"')
        # Inner quotes must occur in pairs
        inner = q[1:-1]
        assert inner.count('"') % 2 == 0
''',
        "behavioral_spec": "SQL identifier escaping must double internal quote characters to prevent quote breakout."
    },
    {
        "id": "task_067_regex_dos_catastrophic_backtrack",
        "category": "security_defect",
        "difficulty": "medium",
        "desc": "Replace catastrophic backtracking regex with linear-time token matcher",
        "expected": "Regex pattern operates in O(N) time without exponential catastrophic backtracking",
        "tags": ["redos", "security", "regex"],
        "repo": "https://github.com/aegis-benchmark/input-validator",
        "commit": "0112233445566778899001122334455667788990",
        "buggy_code": '''import re

# BUG: Nested quantifier (a+)+ causes catastrophic backtracking on non-matching strings
TOKEN_PATTERN = re.compile(r"^([a-zA-Z0-9]+)+$")

def validate_alphanumeric_token(token: str) -> bool:
    """Validates alphanumeric token format."""
    return bool(TOKEN_PATTERN.match(token))
''',
        "fixed_code": '''import re

TOKEN_PATTERN = re.compile(r"^[a-zA-Z0-9]+$")

def validate_alphanumeric_token(token: str) -> bool:
    """Validates alphanumeric token format."""
    return bool(TOKEN_PATTERN.match(token))
''',
        "test_code": '''import pytest
from solution import validate_alphanumeric_token

def test_valid_token():
    assert validate_alphanumeric_token("token123") is True

def test_invalid_characters():
    assert validate_alphanumeric_token("token_123") is False
''',
        "hidden_test_code": '''import pytest
import time
from solution import validate_alphanumeric_token

def test_redos_adversarial_input_fast():
    # Long non-matching token with invalid character at end
    adversarial = "a" * 28 + "!"
    t0 = time.time()
    res = validate_alphanumeric_token(adversarial)
    elapsed = time.time() - t0
    assert res is False
    assert elapsed < 0.2, f"ReDoS vulnerability: took {elapsed:.2f}s"
''',
        "oracle_test_code": '''import pytest
from solution import validate_alphanumeric_token

def test_oracle_token_boundaries():
    assert validate_alphanumeric_token("") is False
    assert validate_alphanumeric_token("A" * 100) is True
    assert validate_alphanumeric_token("A" * 100 + "@") is False
''',
        "behavioral_spec": "Regex validation must complete in linear time without exponential backtracking."
    },
    {
        "id": "task_068_secret_token_timing_attack",
        "category": "security_defect",
        "difficulty": "medium",
        "desc": "Mitigate timing side-channel in cryptographic signature verification",
        "expected": "Uses hmac.compare_digest for constant-time string comparison",
        "tags": ["hmac", "timing-attack", "cryptography"],
        "repo": "https://github.com/aegis-benchmark/auth-service",
        "commit": "1223344556677889900112233445566778899001",
        "buggy_code": '''import hashlib
import hmac

def verify_hmac_signature(payload: bytes, signature_hex: str, secret: str) -> bool:
    """Verifies HMAC SHA-256 signature."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    # BUG: Early-exit string equality leaks timing information
    return signature_hex == expected
''',
        "fixed_code": '''import hashlib
import hmac

def verify_hmac_signature(payload: bytes, signature_hex: str, secret: str) -> bool:
    """Verifies HMAC SHA-256 signature."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_hex, expected)
''',
        "test_code": '''import hashlib
import hmac
import pytest
from solution import verify_hmac_signature

def test_valid_hmac():
    secret = "secret_key"
    payload = b"hello world"
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_hmac_signature(payload, sig, secret) is True
''',
        "hidden_test_code": '''import hashlib
import hmac
import pytest
from solution import verify_hmac_signature

def test_tampered_payload_rejected():
    secret = "secret_key"
    sig = hmac.new(secret.encode(), b"original", hashlib.sha256).hexdigest()
    assert verify_hmac_signature(b"tampered", sig, secret) is False

def test_wrong_signature_length():
    assert verify_hmac_signature(b"data", "short", "key") is False
''',
        "oracle_test_code": '''import pytest
from solution import verify_hmac_signature
import hmac

def test_oracle_constant_time_contract():
    # Verify that verify_hmac_signature uses compare_digest under the hood
    import inspect
    import solution
    src = inspect.getsource(solution.verify_hmac_signature)
    assert "compare_digest" in src
''',
        "behavioral_spec": "HMAC signature evaluation must use constant-time digest comparison to prevent timing attacks."
    }
]
