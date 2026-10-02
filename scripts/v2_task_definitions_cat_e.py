"""
AegisBench v2 MLVerify Expansion: Category E Task Definitions
Focus: Algorithmic Performance / Latency Regression (Tasks 075 - 080)
"""

TASKS_CAT_E = [
    {
        "id": "task_075_quadratic_string_builder_stream",
        "category": "performance_defect",
        "difficulty": "medium",
        "desc": "Optimize quadratic string concatenation in stream reassembly to O(N) linear time",
        "expected": "Uses str.join() buffer to assemble large chunk streams in milliseconds",
        "tags": ["performance", "string-builder", "complexity"],
        "repo": "https://github.com/aegis-benchmark/stream-buffer",
        "commit": "8990011223344556677889900112233445566778",
        "buggy_code": '''from typing import List

def assemble_stream_chunks(chunks: List[str]) -> str:
    """Concatenates list of text chunks into complete document."""
    # BUG: Repeated quadratic string re-allocation in loop O(N^2)
    result = ""
    for chunk in chunks:
        result += chunk
    return result
''',
        "fixed_code": '''from typing import List

def assemble_stream_chunks(chunks: List[str]) -> str:
    """Concatenates list of text chunks into complete document."""
    return "".join(chunks)
''',
        "test_code": '''import pytest
from solution import assemble_stream_chunks

def test_basic_assembly():
    chunks = ["Hello", " ", "World", "!"]
    assert assemble_stream_chunks(chunks) == "Hello World!"
''',
        "hidden_test_code": '''import pytest
import time
from solution import assemble_stream_chunks

def test_linear_scaling_large_stream():
    # 25,000 small chunks
    chunks = ["chunk_data_"] * 25000
    t0 = time.time()
    res = assemble_stream_chunks(chunks)
    elapsed = time.time() - t0
    assert len(res) == 25000 * 11
    # Linear join takes < 0.05s, while quadratic concatenation takes > 0.8s
    assert elapsed < 0.20, f"Quadratic latency bottleneck: took {elapsed:.2f}s"
''',
        "oracle_test_code": '''import pytest
from solution import assemble_stream_chunks

def test_oracle_empty_and_single():
    assert assemble_stream_chunks([]) == ""
    assert assemble_stream_chunks(["only"]) == "only"
''',
        "behavioral_spec": "Stream concatenation must execute in O(N) linear time using buffer join mechanisms."
    },
    {
        "id": "task_076_nested_lookup_linear_scan",
        "category": "performance_defect",
        "difficulty": "medium",
        "desc": "Replace O(N*M) linear membership scan with O(N+M) set-based permission validator",
        "expected": "Builds set index to validate presence of all required privileges in sub-millisecond time",
        "tags": ["performance", "lookup", "set-indexing"],
        "repo": "https://github.com/aegis-benchmark/auth-rbac",
        "commit": "9001122334455667788990011223344556677889",
        "buggy_code": '''from typing import List

def has_required_permissions(assigned_roles: List[str], required_roles: List[str]) -> bool:
    """Verifies whether all required roles are present in assigned roles."""
    # BUG: Linear list scan in inner loop causes O(N * M) quadratic latency on large permission sets
    for req in required_roles:
        if req not in assigned_roles:
            return False
    return True
''',
        "fixed_code": '''from typing import List

def has_required_permissions(assigned_roles: List[str], required_roles: List[str]) -> bool:
    """Verifies whether all required roles are present in assigned roles."""
    assigned_set = set(assigned_roles)
    for req in required_roles:
        if req not in assigned_set:
            return False
    return True
''',
        "test_code": '''import pytest
from solution import has_required_permissions

def test_permissions_met():
    assert has_required_permissions(["read", "write", "admin"], ["read", "write"]) is True

def test_permissions_missing():
    assert has_required_permissions(["read"], ["write"]) is False
''',
        "hidden_test_code": '''import pytest
import time
from solution import has_required_permissions

def test_large_permission_set_performance():
    assigned = [f"role_{i}" for i in range(15000)]
    required = [f"role_{i}" for i in range(5000)]
    t0 = time.time()
    res = has_required_permissions(assigned, required)
    elapsed = time.time() - t0
    assert res is True
    # Set lookup takes < 0.05s, list scans take > 1.0s
    assert elapsed < 0.20, f"Unindexed lookup latency bottleneck: took {elapsed:.2f}s"
''',
        "oracle_test_code": '''import pytest
from solution import has_required_permissions

def test_oracle_empty_requirements():
    assert has_required_permissions([], []) is True
    assert has_required_permissions(["admin"], []) is True
    assert has_required_permissions([], ["admin"]) is False
''',
        "behavioral_spec": "Permission validation must index assigned attributes in a set for O(1) membership queries."
    },
    {
        "id": "task_077_dedup_ordered_list_quadratic",
        "category": "performance_defect",
        "difficulty": "medium",
        "desc": "Implement linear-time order-preserving deduplication using auxiliary hash set",
        "expected": "Deduplicates list in O(N) time while strictly maintaining first-seen relative order",
        "tags": ["performance", "dedup", "order-preserving"],
        "repo": "https://github.com/aegis-benchmark/data-pipeline",
        "commit": "0112233445566778899001122334455667788990",
        "buggy_code": '''from typing import List

def deduplicate_preserve_order(items: List[int]) -> List[int]:
    """Deduplicates list while preserving first appearance order."""
    # BUG: Quadratic lookup 'if x not in seen' on list causes O(N^2) slowdown
    seen = []
    for x in items:
        if x not in seen:
            seen.append(x)
    return seen
''',
        "fixed_code": '''from typing import List

def deduplicate_preserve_order(items: List[int]) -> List[int]:
    """Deduplicates list while preserving first appearance order."""
    seen_set = set()
    result = []
    for x in items:
        if x not in seen_set:
            seen_set.add(x)
            result.append(x)
    return result
''',
        "test_code": '''import pytest
from solution import deduplicate_preserve_order

def test_small_dedup():
    assert deduplicate_preserve_order([3, 1, 2, 3, 1, 4]) == [3, 1, 2, 4]
''',
        "hidden_test_code": '''import pytest
import time
from solution import deduplicate_preserve_order

def test_large_list_dedup_performance():
    # 20,000 integers with repeats
    data = [i % 500 for i in range(20000)]
    t0 = time.time()
    res = deduplicate_preserve_order(data)
    elapsed = time.time() - t0
    assert len(res) == 500
    assert res[:5] == [0, 1, 2, 3, 4]
    # Set-based dedup takes < 0.05s, list membership takes > 0.8s
    assert elapsed < 0.20, f"Quadratic dedup latency: took {elapsed:.2f}s"
''',
        "oracle_test_code": '''import pytest
from solution import deduplicate_preserve_order

def test_oracle_empty_and_uniform():
    assert deduplicate_preserve_order([]) == []
    assert deduplicate_preserve_order([7, 7, 7, 7]) == [7]
''',
        "behavioral_spec": "Deduplication must maintain stable ordering while bounding execution time to O(N)."
    },
    {
        "id": "task_078_recursive_fibonacci_memo_leak",
        "category": "performance_defect",
        "difficulty": "medium",
        "desc": "Optimize grid unique path counter from exponential O(2^(M+N)) recursion to linear DP",
        "expected": "Calculates unique grid paths in linear time without stack overflow or exponential explosion",
        "tags": ["dynamic-programming", "complexity", "grid-paths"],
        "repo": "https://github.com/aegis-benchmark/combinatorics",
        "commit": "1223344556677889900112233445566778899001",
        "buggy_code": '''def count_unique_grid_paths(m: int, n: int) -> int:
    """Counts unique paths from top-left (0,0) to bottom-right (m-1, n-1) on m x n grid."""
    if m <= 0 or n <= 0:
        return 0
    # BUG: Naive double recursion without memoization causes O(2^(m+n)) explosion
    if m == 1 or n == 1:
        return 1
    return count_unique_grid_paths(m - 1, n) + count_unique_grid_paths(m, n - 1)
''',
        "fixed_code": '''import math

def count_unique_grid_paths(m: int, n: int) -> int:
    """Counts unique paths from top-left (0,0) to bottom-right (m-1, n-1) on m x n grid."""
    if m <= 0 or n <= 0:
        return 0
    # Math closed form: (m+n-2) choose (m-1)
    return math.comb(m + n - 2, m - 1)
''',
        "test_code": '''import pytest
from solution import count_unique_grid_paths

def test_tiny_grid():
    assert count_unique_grid_paths(3, 2) == 3
    assert count_unique_grid_paths(3, 7) == 28
''',
        "hidden_test_code": '''import pytest
import time
from solution import count_unique_grid_paths

def test_moderate_grid_fast():
    t0 = time.time()
    ans = count_unique_grid_paths(18, 18)
    elapsed = time.time() - t0
    assert ans == 2333606220
    # Exponential recursion would take > 60s, closed-form takes < 0.01s
    assert elapsed < 0.20, f"Combinatorial explosion: took {elapsed:.2f}s"
''',
        "oracle_test_code": '''import pytest
from solution import count_unique_grid_paths

def test_oracle_boundary_dimensions():
    assert count_unique_grid_paths(1, 100) == 1
    assert count_unique_grid_paths(100, 1) == 1
    assert count_unique_grid_paths(0, 5) == 0
''',
        "behavioral_spec": "Grid path calculation must use dynamic programming or closed-form math to avoid combinatorial explosion."
    },
    {
        "id": "task_079_regex_compile_in_loop",
        "category": "performance_defect",
        "difficulty": "medium",
        "desc": "Hoist regex compilation outside inner log processing loop to prevent compilation churn",
        "expected": "Pre-compiles regex once to process thousands of log entries efficiently",
        "tags": ["regex", "performance", "log-parsing"],
        "repo": "https://github.com/aegis-benchmark/log-indexer",
        "commit": "2334455667788990011223344556677889900112",
        "buggy_code": '''import re
from typing import List

def extract_log_severities(lines: List[str]) -> List[str]:
    """Extracts severity tags [INFO], [WARN], [ERROR] from log stream."""
    severities = []
    # BUG: Compiles regex on every single line inside the loop
    for line in lines:
        pattern = re.compile(r"\\[(INFO|WARN|ERROR)\\]")
        match = pattern.search(line)
        if match:
            severities.append(match.group(1))
    return severities
''',
        "fixed_code": '''import re
from typing import List

LOG_SEVERITY_PATTERN = re.compile(r"\\[(INFO|WARN|ERROR)\\]")

def extract_log_severities(lines: List[str]) -> List[str]:
    """Extracts severity tags [INFO], [WARN], [ERROR] from log stream."""
    severities = []
    for line in lines:
        match = LOG_SEVERITY_PATTERN.search(line)
        if match:
            severities.append(match.group(1))
    return severities
''',
        "test_code": '''import pytest
from solution import extract_log_severities

def test_basic_extraction():
    lines = ["[INFO] Started worker", "Malformed line", "[ERROR] Connection lost"]
    assert extract_log_severities(lines) == ["INFO", "ERROR"]
''',
        "hidden_test_code": '''import pytest
import time
from solution import extract_log_severities

def test_large_log_throughput():
    lines = [f"2026-09-27 [{ 'INFO' if i%2==0 else 'ERROR' }] message {i}" for i in range(25000)]
    t0 = time.time()
    res = extract_log_severities(lines)
    elapsed = time.time() - t0
    assert len(res) == 25000
    # Pre-compiled takes < 0.10s, per-line compilation takes > 0.8s
    assert elapsed < 0.25, f"Regex compilation churn: took {elapsed:.2f}s"
''',
        "oracle_test_code": '''import pytest
from solution import extract_log_severities

def test_oracle_empty_input():
    assert extract_log_severities([]) == []
''',
        "behavioral_spec": "Regular expressions in tight batch loops must be pre-compiled to avoid engine instantiation overhead."
    },
    {
        "id": "task_080_unbuffered_file_byte_writer",
        "category": "performance_defect",
        "difficulty": "medium",
        "desc": "Serialize byte payload records using contiguous buffer join rather than byte-by-byte concatenation",
        "expected": "Assembles serialized byte stream in linear time using b''.join()",
        "tags": ["io", "performance", "byte-buffer"],
        "repo": "https://github.com/aegis-benchmark/proto-pack",
        "commit": "3445566778899001122334455667788990011223",
        "buggy_code": '''from typing import List

def pack_binary_frames(frames: List[bytes]) -> bytes:
    """Packs binary frames into contiguous payload."""
    # BUG: byte-by-byte accumulation repeatedly re-allocates immutable bytes object
    output = b""
    for frame in frames:
        output = output + frame
    return output
''',
        "fixed_code": '''from typing import List

def pack_binary_frames(frames: List[bytes]) -> bytes:
    """Packs binary frames into contiguous payload."""
    return b"".join(frames)
''',
        "test_code": '''import pytest
from solution import pack_binary_frames

def test_small_frames():
    frames = [b"\\x01\\x02", b"\\x03\\x04"]
    assert pack_binary_frames(frames) == b"\\x01\\x02\\x03\\x04"
''',
        "hidden_test_code": '''import pytest
import time
from solution import pack_binary_frames

def test_large_frame_throughput():
    frames = [b"FRAME_HEADER_PAYLOAD_CHUNK_" for _ in range(30000)]
    t0 = time.time()
    packed = pack_binary_frames(frames)
    elapsed = time.time() - t0
    assert len(packed) == 30000 * 27
    # Join takes < 0.05s, repeated concatenation takes > 0.9s
    assert elapsed < 0.20, f"Unbuffered byte allocation latency: took {elapsed:.2f}s"
''',
        "oracle_test_code": '''import pytest
from solution import pack_binary_frames

def test_oracle_empty_frames():
    assert pack_binary_frames([]) == b""
    assert pack_binary_frames([b"", b""]) == b""
''',
        "behavioral_spec": "Binary frame serialization must use contiguous buffer concatenation to minimize allocations."
    }
]
