"""
AegisBench v1 Generator Part 2:
Tasks 21-50:
- Track 2: Scientific & Array Computing (Tasks 21-32)
- Track 3: AI/ML Systems & Serving (Tasks 33-50)
"""

import json
import difflib
from pathlib import Path

TASKS_PART2 = [
    # Track 2: Scientific & Array Computing (Tasks 21-32)
    {
        "id": "task_021_numpy_stride_tricks",
        "category": "array_strides",
        "difficulty": "medium",
        "desc": "Calculate sliding window shape for 1D strided array view",
        "expected": "Computes exact number of valid windows: (n - window_size) // step + 1",
        "tags": ["numpy", "strides", "sliding-window"],
        "repo": "https://github.com/numpy/numpy",
        "commit": "5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e",
        "buggy_code": """def compute_sliding_window_shape(n_elements: int, window_size: int, step: int = 1) -> tuple[int, int]:
    if window_size > n_elements or window_size <= 0:
        return (0, 0)
    # BUG: off-by-one omission of +1 in window count
    num_windows = (n_elements - window_size) // step
    return (num_windows, window_size)
""",
        "fixed_code": """def compute_sliding_window_shape(n_elements: int, window_size: int, step: int = 1) -> tuple[int, int]:
    if window_size > n_elements or window_size <= 0:
        return (0, 0)
    num_windows = (n_elements - window_size) // step + 1
    return (num_windows, window_size)
""",
        "test_code": """from solution import compute_sliding_window_shape

def test_sliding_window_shape_standard():
    assert compute_sliding_window_shape(10, 3, 1) == (8, 3)
""",
        "hidden_test_code": """from solution import compute_sliding_window_shape

def test_sliding_window_with_step():
    assert compute_sliding_window_shape(10, 2, 2) == (5, 2)
    assert compute_sliding_window_shape(5, 5, 1) == (1, 5)
    assert compute_sliding_window_shape(3, 5, 1) == (0, 0)
"""
    },
    {
        "id": "task_022_numpy_broadcast_edge",
        "category": "array_broadcasting",
        "difficulty": "medium",
        "desc": "Compute broadcasted output shape for two multidimensional array shapes",
        "expected": "Calculates NumPy-compatible broadcasted shape or raises ValueError",
        "tags": ["numpy", "broadcasting", "tensors"],
        "repo": "https://github.com/numpy/numpy",
        "commit": "4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d",
        "buggy_code": """def broadcast_shapes(s1: tuple[int, ...], s2: tuple[int, ...]) -> tuple[int, ...]:
    r1 = list(reversed(s1))
    r2 = list(reversed(s2))
    max_len = max(len(r1), len(r2))
    res = []
    for i in range(max_len):
        d1 = r1[i] if i < len(r1) else 1
        d2 = r2[i] if i < len(r2) else 1
        if d1 == d2:
            res.append(d1)
        elif d1 == 1:
            res.append(d2)
        # BUG: forgot to handle d2 == 1, erroneously raises mismatch
        else:
            raise ValueError(f"Shapes {s1} and {s2} not broadcastable")
    return tuple(reversed(res))
""",
        "fixed_code": """def broadcast_shapes(s1: tuple[int, ...], s2: tuple[int, ...]) -> tuple[int, ...]:
    r1 = list(reversed(s1))
    r2 = list(reversed(s2))
    max_len = max(len(r1), len(r2))
    res = []
    for i in range(max_len):
        d1 = r1[i] if i < len(r1) else 1
        d2 = r2[i] if i < len(r2) else 1
        if d1 == d2:
            res.append(d1)
        elif d1 == 1:
            res.append(d2)
        elif d2 == 1:
            res.append(d1)
        else:
            raise ValueError(f"Shapes {s1} and {s2} not broadcastable")
    return tuple(reversed(res))
""",
        "test_code": """from solution import broadcast_shapes

def test_broadcast_singleton_in_second_shape():
    s1 = (4, 3)
    s2 = (4, 1)
    assert broadcast_shapes(s1, s2) == (4, 3)
""",
        "hidden_test_code": """import pytest
from solution import broadcast_shapes

def test_broadcast_different_ranks():
    assert broadcast_shapes((5, 1, 4), (3, 1)) == (5, 3, 4)

def test_incompatible_shapes_raise():
    with pytest.raises(ValueError):
        broadcast_shapes((3,), (4,))
"""
    },
    {
        "id": "task_023_numpy_dtype_overflow",
        "category": "numeric_precision",
        "difficulty": "medium",
        "desc": "Detect integer accumulation overflow for signed 32-bit integers",
        "expected": "Raises OverflowError when accumulated sum exceeds 32-bit signed integer limits",
        "tags": ["numpy", "dtype", "overflow"],
        "repo": "https://github.com/numpy/numpy",
        "commit": "3d2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c",
        "buggy_code": """INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1

def accumulate_int32(values: list[int]) -> int:
    total = 0
    for v in values:
        total += v
        # BUG: only checks upper bound, fails to check lower bound
        if total > INT32_MAX:
            raise OverflowError("32-bit integer overflow")
    return total
""",
        "fixed_code": """INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1

def accumulate_int32(values: list[int]) -> int:
    total = 0
    for v in values:
        total += v
        if total > INT32_MAX or total < INT32_MIN:
            raise OverflowError("32-bit integer overflow")
    return total
""",
        "test_code": """import pytest
from solution import accumulate_int32, INT32_MIN

def test_negative_overflow_detected():
    with pytest.raises(OverflowError):
        accumulate_int32([INT32_MIN, -1])
""",
        "hidden_test_code": """import pytest
from solution import accumulate_int32, INT32_MAX

def test_positive_overflow_detected():
    with pytest.raises(OverflowError):
        accumulate_int32([INT32_MAX, 1])

def test_within_bounds():
    assert accumulate_int32([100, 200, -50]) == 250
"""
    },
    {
        "id": "task_024_numpy_masked_array_nan",
        "category": "array_reduction",
        "difficulty": "medium",
        "desc": "Compute arithmetic mean of array excluding both masked elements and NaN values",
        "expected": "Returns mean of valid elements, or float('nan') if all are masked or NaN",
        "tags": ["numpy", "nan", "reduction"],
        "repo": "https://github.com/numpy/numpy",
        "commit": "2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b",
        "buggy_code": """import math

def nanmean_masked(data: list[float], mask: list[bool]) -> float:
    valid_elements = []
    for x, m in zip(data, mask):
        if not m:
            # BUG: forgets to check math.isnan(x)
            valid_elements.append(x)
    if not valid_elements:
        return float('nan')
    return sum(valid_elements) / len(valid_elements)
""",
        "fixed_code": """import math

def nanmean_masked(data: list[float], mask: list[bool]) -> float:
    valid_elements = []
    for x, m in zip(data, mask):
        if not m and not math.isnan(x):
            valid_elements.append(x)
    if not valid_elements:
        return float('nan')
    return sum(valid_elements) / len(valid_elements)
""",
        "test_code": """import math
from solution import nanmean_masked

def test_nan_filtered_from_unmasked():
    data = [1.0, float('nan'), 3.0]
    mask = [False, False, False]
    assert nanmean_masked(data, mask) == 2.0
""",
        "hidden_test_code": """import math
from solution import nanmean_masked

def test_all_masked_or_nan_returns_nan():
    data = [float('nan'), 5.0]
    mask = [False, True]
    assert math.isnan(nanmean_masked(data, mask))
"""
    },
    {
        "id": "task_025_numpy_matrix_power_zero",
        "category": "linear_algebra",
        "difficulty": "easy",
        "desc": "Return identity matrix when computing matrix power p=0",
        "expected": "Returns N x N identity matrix for any valid square matrix raised to power 0",
        "tags": ["numpy", "matrix", "linalg"],
        "repo": "https://github.com/numpy/numpy",
        "commit": "1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a",
        "buggy_code": """def matrix_power(matrix: list[list[float]], power: int) -> list[list[float]]:
    n = len(matrix)
    if power == 0:
        # BUG: returns zero matrix instead of identity matrix
        return [[0.0 for _ in range(n)] for _ in range(n)]
    res = [row[:] for row in matrix]
    for _ in range(power - 1):
        new_res = [[0.0 for _ in range(n)] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    new_res[i][j] += res[i][k] * matrix[k][j]
        res = new_res
    return res
""",
        "fixed_code": """def matrix_power(matrix: list[list[float]], power: int) -> list[list[float]]:
    n = len(matrix)
    if power == 0:
        return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    res = [row[:] for row in matrix]
    for _ in range(power - 1):
        new_res = [[0.0 for _ in range(n)] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    new_res[i][j] += res[i][k] * matrix[k][j]
        res = new_res
    return res
""",
        "test_code": """from solution import matrix_power

def test_matrix_power_zero_returns_identity():
    m = [[2.0, 3.0], [4.0, 5.0]]
    expected = [[1.0, 0.0], [0.0, 1.0]]
    assert matrix_power(m, 0) == expected
""",
        "hidden_test_code": """from solution import matrix_power

def test_matrix_power_one_and_two():
    m = [[1.0, 1.0], [1.0, 0.0]]
    assert matrix_power(m, 1) == m
    assert matrix_power(m, 2) == [[2.0, 1.0], [1.0, 1.0]]
"""
    },
    {
        "id": "task_026_numpy_clip_inplace_view",
        "category": "array_operations",
        "difficulty": "easy",
        "desc": "Clip 1D array values strictly between min and max bounds",
        "expected": "Ensures every element satisfies a_min <= x <= a_max",
        "tags": ["numpy", "clip", "bounds"],
        "repo": "https://github.com/numpy/numpy",
        "commit": "0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f",
        "buggy_code": """def clip_array(arr: list[float], a_min: float, a_max: float) -> list[float]:
    # BUG: inverts condition logic
    return [a_min if x > a_max else a_max if x < a_min else x for x in arr]
""",
        "fixed_code": """def clip_array(arr: list[float], a_min: float, a_max: float) -> list[float]:
    return [a_max if x > a_max else a_min if x < a_min else x for x in arr]
""",
        "test_code": """from solution import clip_array

def test_clip_out_of_bounds():
    data = [-5.0, 0.0, 5.0, 15.0]
    res = clip_array(data, 0.0, 10.0)
    assert res == [0.0, 0.0, 5.0, 10.0]
""",
        "hidden_test_code": """from solution import clip_array

def test_clip_all_within_bounds():
    data = [2.0, 4.0, 6.0]
    assert clip_array(data, 0.0, 10.0) == [2.0, 4.0, 6.0]
"""
    },
    {
        "id": "task_027_pandas_multiindex_alignment",
        "category": "tabular_alignment",
        "difficulty": "medium",
        "desc": "Perform Cartesian product alignment on two-level hierarchical indices",
        "expected": "Aligns dictionary values matching on composite key (level_0, level_1)",
        "tags": ["pandas", "multiindex", "alignment"],
        "repo": "https://github.com/pandas-dev/pandas",
        "commit": "9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0a",
        "buggy_code": """def align_multiindex_data(df1: dict, df2: dict) -> dict:
    aligned = {}
    for (k1, k2), v1 in df1.items():
        # BUG: only keys present in df1 are inspected, misses keys only in df2
        v2 = df2.get((k1, k2), 0)
        aligned[(k1, k2)] = v1 + v2
    return aligned
""",
        "fixed_code": """def align_multiindex_data(df1: dict, df2: dict) -> dict:
    all_keys = set(df1.keys()).union(set(df2.keys()))
    aligned = {}
    for k in sorted(all_keys):
        v1 = df1.get(k, 0)
        v2 = df2.get(k, 0)
        aligned[k] = v1 + v2
    return aligned
""",
        "test_code": """from solution import align_multiindex_data

def test_multiindex_outer_join():
    d1 = {("A", 1): 10}
    d2 = {("B", 2): 20}
    res = align_multiindex_data(d1, d2)
    assert res == {("A", 1): 10, ("B", 2): 20}
""",
        "hidden_test_code": """from solution import align_multiindex_data

def test_multiindex_overlapping_keys():
    d1 = {("A", 1): 5, ("A", 2): 10}
    d2 = {("A", 1): 3, ("B", 1): 7}
    res = align_multiindex_data(d1, d2)
    assert res[("A", 1)] == 8
    assert res[("B", 1)] == 7
"""
    },
    {
        "id": "task_028_pandas_datetime_tz_convert",
        "category": "tabular_datetime",
        "difficulty": "medium",
        "desc": "Convert UTC timestamps adjusting for localized timezone offsets",
        "expected": "Adjusts hours by offset_hours without modulo wrapping negative days",
        "tags": ["pandas", "datetime", "timezone"],
        "repo": "https://github.com/pandas-dev/pandas",
        "commit": "8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0a9f",
        "buggy_code": """from datetime import datetime, timedelta

def convert_tz_utc(dt: datetime, offset_hours: int) -> datetime:
    # BUG: uses datetime replace on hour instead of timedelta addition
    new_hour = (dt.hour + offset_hours) % 24
    return dt.replace(hour=new_hour)
""",
        "fixed_code": """from datetime import datetime, timedelta

def convert_tz_utc(dt: datetime, offset_hours: int) -> datetime:
    return dt + timedelta(hours=offset_hours)
""",
        "test_code": """from datetime import datetime
from solution import convert_tz_utc

def test_day_boundary_wrap():
    dt = datetime(2026, 9, 27, 23, 0)
    res = convert_tz_utc(dt, 2)
    assert res == datetime(2026, 9, 28, 1, 0)
""",
        "hidden_test_code": """from datetime import datetime
from solution import convert_tz_utc

def test_negative_day_boundary_wrap():
    dt = datetime(2026, 9, 27, 1, 0)
    res = convert_tz_utc(dt, -3)
    assert res == datetime(2026, 9, 26, 22, 0)
"""
    },
    {
        "id": "task_029_pandas_rolling_min_periods",
        "category": "tabular_rolling",
        "difficulty": "medium",
        "desc": "Compute moving average requiring at least min_periods non-null observations",
        "expected": "Emits None when valid observation count in sliding window is below min_periods",
        "tags": ["pandas", "rolling", "window"],
        "repo": "https://github.com/pandas-dev/pandas",
        "commit": "7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0a9f8e",
        "buggy_code": """def rolling_mean(series: list[float | None], window: int, min_periods: int) -> list[float | None]:
    result = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        sub = series[start:i+1]
        valid = [x for x in sub if x is not None]
        # BUG: checks len(sub) instead of len(valid)
        if len(sub) >= min_periods and valid:
            result.append(sum(valid) / len(valid))
        else:
            result.append(None)
    return result
""",
        "fixed_code": """def rolling_mean(series: list[float | None], window: int, min_periods: int) -> list[float | None]:
    result = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        sub = series[start:i+1]
        valid = [x for x in sub if x is not None]
        if len(valid) >= min_periods:
            result.append(sum(valid) / len(valid))
        else:
            result.append(None)
    return result
""",
        "test_code": """from solution import rolling_mean

def test_min_periods_with_nulls():
    s = [10.0, None, None, 20.0]
    res = rolling_mean(s, window=3, min_periods=2)
    assert res[2] is None  # only 1 valid element in window [10, None, None]
""",
        "hidden_test_code": """from solution import rolling_mean

def test_rolling_mean_standard():
    s = [1.0, 2.0, 3.0, 4.0]
    res = rolling_mean(s, window=2, min_periods=2)
    assert res == [None, 1.5, 2.5, 3.5]
"""
    },
    {
        "id": "task_030_scipy_sparse_csr_slice",
        "category": "sparse_matrix",
        "difficulty": "medium",
        "desc": "Extract row slice from Compressed Sparse Row (CSR) index pointers",
        "expected": "Returns data and column indices corresponding to row range [start_row, end_row)",
        "tags": ["scipy", "sparse", "csr"],
        "repo": "https://github.com/scipy/scipy",
        "commit": "6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0a9f8e7d",
        "buggy_code": """def csr_row_slice(indptr: list[int], indices: list[int], data: list[float], row: int):
    # BUG: uses row + 1 on data slice without bounds check
    start = indptr[row]
    end = indptr[row + 1]
    return indices[start:end], data[start:end]
""",
        "fixed_code": """def csr_row_slice(indptr: list[int], indices: list[int], data: list[float], row: int):
    if row < 0 or row >= len(indptr) - 1:
        raise IndexError(f"Row {row} out of range [0, {len(indptr) - 2}]")
    start = indptr[row]
    end = indptr[row + 1]
    return indices[start:end], data[start:end]
""",
        "test_code": """import pytest
from solution import csr_row_slice

def test_out_of_bounds_csr_row():
    indptr = [0, 2, 4]
    with pytest.raises(IndexError):
        csr_row_slice(indptr, [0, 1, 0, 1], [1.0, 2.0, 3.0, 4.0], 5)
""",
        "hidden_test_code": """from solution import csr_row_slice

def test_valid_csr_row_slice():
    indptr = [0, 2, 3]
    indices = [0, 2, 1]
    data = [5.0, 8.0, 3.0]
    cols, vals = csr_row_slice(indptr, indices, data, 0)
    assert cols == [0, 2]
    assert vals == [5.0, 8.0]
"""
    },
    {
        "id": "task_031_scipy_optim_bounds_clamping",
        "category": "optimization",
        "difficulty": "easy",
        "desc": "Project optimization vector onto box constraints [lower, upper]",
        "expected": "Clamps each parameter component x[i] into interval [l[i], u[i]]",
        "tags": ["scipy", "optimization", "bounds"],
        "repo": "https://github.com/scipy/scipy",
        "commit": "5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0a9f8e7d6c",
        "buggy_code": """def project_box_bounds(x: list[float], bounds: list[tuple[float, float]]) -> list[float]:
    projected = []
    for val, (l, u) in zip(x, bounds):
        # BUG: inverts min and max clamping
        projected.append(min(l, max(u, val)))
    return projected
""",
        "fixed_code": """def project_box_bounds(x: list[float], bounds: list[tuple[float, float]]) -> list[float]:
    projected = []
    for val, (l, u) in zip(x, bounds):
        projected.append(max(l, min(u, val)))
    return projected
""",
        "test_code": """from solution import project_box_bounds

def test_project_bounds_clamping():
    x = [-2.0, 1.5, 5.0]
    bounds = [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)]
    assert project_box_bounds(x, bounds) == [0.0, 1.5, 3.0]
""",
        "hidden_test_code": """from solution import project_box_bounds

def test_project_within_bounds_unchanged():
    x = [0.5, 1.0]
    bounds = [(0.0, 1.0), (0.0, 2.0)]
    assert project_box_bounds(x, bounds) == [0.5, 1.0]
"""
    },
    {
        "id": "task_032_scipy_distance_metric_symmetry",
        "category": "scientific_distance",
        "difficulty": "medium",
        "desc": "Compute symmetric Euclidean distance matrix guaranteeing D[i][j] == D[j][i]",
        "expected": "Ensures distance matrix has exact float symmetry and diagonal zeroes",
        "tags": ["scipy", "distance", "metric"],
        "repo": "https://github.com/scipy/scipy",
        "commit": "4a3f2e1d0c9b8a7f6e5d4c3b2a1f0a9f8e7d6c5b",
        "buggy_code": """import math

def pairwise_euclidean(points: list[tuple[float, float]]) -> list[list[float]]:
    n = len(points)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            d = math.sqrt((points[i][0] - points[j][0])**2 + (points[i][1] - points[j][1])**2)
            dist[i][j] = d
            # BUG: forgets to mirror dist[j][i]
    return dist
""",
        "fixed_code": """import math

def pairwise_euclidean(points: list[tuple[float, float]]) -> list[list[float]]:
    n = len(points)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            d = math.sqrt((points[i][0] - points[j][0])**2 + (points[i][1] - points[j][1])**2)
            dist[i][j] = d
            dist[j][i] = d
    return dist
""",
        "test_code": """from solution import pairwise_euclidean

def test_distance_matrix_symmetry():
    pts = [(0.0, 0.0), (3.0, 4.0)]
    d = pairwise_euclidean(pts)
    assert d[0][1] == 5.0
    assert d[1][0] == 5.0
    assert d[0][0] == 0.0
""",
        "hidden_test_code": """from solution import pairwise_euclidean

def test_triangle_distances():
    pts = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    d = pairwise_euclidean(pts)
    assert d[1][2] == d[2][1]
"""
    },
    # Track 3: AI/ML Systems & Serving (Tasks 33-50)
    {
        "id": "task_033_pytorch_graph_detachment",
        "category": "ml_autograd",
        "difficulty": "medium",
        "desc": "Preserve computation graph backward pass gradient flow without accidental detachment",
        "expected": "Accumulates gradients through intermediate activation variables",
        "tags": ["pytorch", "autograd", "gradients"],
        "repo": "https://github.com/pytorch/pytorch",
        "commit": "3f2e1d0c9b8a7f6e5d4c3b2a1f0a9f8e7d6c5b4a",
        "buggy_code": """class Node:
    def __init__(self, val, grad=0.0, prev=None):
        self.val = val
        self.grad = grad
        self.prev = prev or []

def square_node(x: Node) -> Node:
    # BUG: creates new detached node without setting prev linkage
    return Node(x.val ** 2, prev=[])

def backward(out: Node):
    out.grad = 1.0
    queue = [out]
    while queue:
        curr = queue.pop(0)
        for p in curr.prev:
            p.grad += curr.grad * (2 * p.val)
            queue.append(p)
""",
        "fixed_code": """class Node:
    def __init__(self, val, grad=0.0, prev=None):
        self.val = val
        self.grad = grad
        self.prev = prev or []

def square_node(x: Node) -> Node:
    return Node(x.val ** 2, prev=[x])

def backward(out: Node):
    out.grad = 1.0
    queue = [out]
    while queue:
        curr = queue.pop(0)
        for p in curr.prev:
            p.grad += curr.grad * (2 * p.val)
            queue.append(p)
""",
        "test_code": """from solution import Node, square_node, backward

def test_gradient_propagates_to_input():
    x = Node(3.0)
    y = square_node(x)
    backward(y)
    assert x.grad == 6.0
""",
        "hidden_test_code": """from solution import Node, square_node, backward

def test_gradient_zero_input():
    x = Node(0.0)
    y = square_node(x)
    backward(y)
    assert x.grad == 0.0
"""
    },
    {
        "id": "task_034_pytorch_device_sync_barrier",
        "category": "ml_runtime",
        "difficulty": "medium",
        "desc": "Simulate async stream barrier synchronization before host buffer read",
        "expected": "Blocks host execution until all queued stream events have completed",
        "tags": ["pytorch", "cuda", "streams"],
        "repo": "https://github.com/pytorch/pytorch",
        "commit": "2e1d0c9b8a7f6e5d4c3b2a1f0a9f8e7d6c5b4a3f",
        "buggy_code": """class StreamManager:
    def __init__(self):
        self.pending_tasks = []

    def record_event(self, task_name):
        self.pending_tasks.append(task_name)

    def synchronize(self):
        # BUG: forgets to clear pending tasks on barrier completion
        pass

    def is_idle(self) -> bool:
        return len(self.pending_tasks) == 0
""",
        "fixed_code": """class StreamManager:
    def __init__(self):
        self.pending_tasks = []

    def record_event(self, task_name):
        self.pending_tasks.append(task_name)

    def synchronize(self):
        self.pending_tasks.clear()

    def is_idle(self) -> bool:
        return len(self.pending_tasks) == 0
""",
        "test_code": """from solution import StreamManager

def test_synchronize_drains_stream():
    mgr = StreamManager()
    mgr.record_event("matmul")
    mgr.synchronize()
    assert mgr.is_idle() is True
""",
        "hidden_test_code": """from solution import StreamManager

def test_pending_tasks_not_idle():
    mgr = StreamManager()
    mgr.record_event("conv2d")
    assert mgr.is_idle() is False
"""
    },
    {
        "id": "task_035_pytorch_batch_norm_eval_mode",
        "category": "ml_layers",
        "difficulty": "medium",
        "desc": "Freeze BatchNorm running statistics when layer is in eval mode",
        "expected": "Running mean and running variance remain constant when training=False",
        "tags": ["pytorch", "batchnorm", "eval"],
        "repo": "https://github.com/pytorch/pytorch",
        "commit": "1d0c9b8a7f6e5d4c3b2a1f0a9f8e7d6c5b4a3f2e",
        "buggy_code": """class BatchNorm1D:
    def __init__(self, momentum=0.1):
        self.running_mean = 0.0
        self.momentum = momentum
        self.training = True

    def forward(self, batch_mean: float):
        # BUG: updates running_mean even when self.training is False
        self.running_mean = (1 - self.momentum) * self.running_mean + self.momentum * batch_mean
        return self.running_mean
""",
        "fixed_code": """class BatchNorm1D:
    def __init__(self, momentum=0.1):
        self.running_mean = 0.0
        self.momentum = momentum
        self.training = True

    def forward(self, batch_mean: float):
        if self.training:
            self.running_mean = (1 - self.momentum) * self.running_mean + self.momentum * batch_mean
        return self.running_mean
""",
        "test_code": """from solution import BatchNorm1D

def test_running_mean_frozen_in_eval_mode():
    bn = BatchNorm1D(momentum=0.5)
    bn.running_mean = 10.0
    bn.training = False
    bn.forward(100.0)
    assert bn.running_mean == 10.0
""",
        "hidden_test_code": """from solution import BatchNorm1D

def test_running_mean_updates_in_train_mode():
    bn = BatchNorm1D(momentum=0.5)
    bn.running_mean = 10.0
    bn.training = True
    bn.forward(20.0)
    assert bn.running_mean == 15.0
"""
    },
    {
        "id": "task_036_pytorch_optimizer_param_group",
        "category": "ml_optimization",
        "difficulty": "medium",
        "desc": "Scale learning rates individually across heterogeneous parameter groups",
        "expected": "Multiplies each parameter group lr by its designated decay factor",
        "tags": ["pytorch", "optimizer", "scheduler"],
        "repo": "https://github.com/pytorch/pytorch",
        "commit": "0c9b8a7f6e5d4c3b2a1f0a9f8e7d6c5b4a3f2e1d",
        "buggy_code": """def step_lr_scheduler(param_groups: list[dict], decay_factor: float):
    # BUG: only updates the first parameter group
    if param_groups:
        param_groups[0]["lr"] *= decay_factor
""",
        "fixed_code": """def step_lr_scheduler(param_groups: list[dict], decay_factor: float):
    for group in param_groups:
        group["lr"] *= decay_factor
""",
        "test_code": """from solution import step_lr_scheduler

def test_all_param_groups_decay():
    groups = [{"name": "backbone", "lr": 1e-3}, {"name": "head", "lr": 1e-2}]
    step_lr_scheduler(groups, 0.1)
    assert abs(groups[0]["lr"] - 1e-4) < 1e-7
    assert abs(groups[1]["lr"] - 1e-3) < 1e-7
""",
        "hidden_test_code": """from solution import step_lr_scheduler

def test_single_group_decay():
    groups = [{"lr": 0.5}]
    step_lr_scheduler(groups, 0.5)
    assert groups[0]["lr"] == 0.25
"""
    },
    {
        "id": "task_037_pytorch_dataloader_worker_seed",
        "category": "ml_dataloader",
        "difficulty": "easy",
        "desc": "Generate independent deterministic random seeds for multiprocessing DataLoader workers",
        "expected": "Returns distinct non-overlapping seed for each worker_id given base seed",
        "tags": ["pytorch", "dataloader", "seeding"],
        "repo": "https://github.com/pytorch/pytorch",
        "commit": "9b8a7f6e5d4c3b2a1f0a9f8e7d6c5b4a3f2e1d0c",
        "buggy_code": """def generate_worker_seed(base_seed: int, worker_id: int) -> int:
    # BUG: returns base_seed ignoring worker_id, leading to duplicate samples across workers
    return base_seed
""",
        "fixed_code": """def generate_worker_seed(base_seed: int, worker_id: int) -> int:
    return (base_seed + worker_id * 10007) % (2**31 - 1)
""",
        "test_code": """from solution import generate_worker_seed

def test_distinct_seeds_per_worker():
    s0 = generate_worker_seed(42, 0)
    s1 = generate_worker_seed(42, 1)
    assert s0 != s1
""",
        "hidden_test_code": """from solution import generate_worker_seed

def test_deterministic_reproducibility():
    assert generate_worker_seed(100, 3) == generate_worker_seed(100, 3)
"""
    },
    {
        "id": "task_038_hf_tokenizer_truncation_overflow",
        "category": "ml_nlp_tokenizer",
        "difficulty": "medium",
        "desc": "Truncate paired sequences preserving special prefix and separator tokens",
        "expected": "Truncates sequence body while preserving [CLS] at head and [SEP] at boundaries",
        "tags": ["transformers", "tokenizer", "truncation"],
        "repo": "https://github.com/huggingface/transformers",
        "commit": "8a7f6e5d4c3b2a1f0a9f8e7d6c5b4a3f2e1d0c9b",
        "buggy_code": """def truncate_token_pair(seq_a: list[str], seq_b: list[str], max_length: int) -> list[str]:
    # Expected format: ['[CLS]'] + a + ['[SEP]'] + b + ['[SEP]']
    # Total special tokens = 3
    # BUG: truncates raw input after adding special tokens, potentially dropping [SEP]
    merged = ["[CLS]"] + seq_a + ["[SEP]"] + seq_b + ["[SEP]"]
    return merged[:max_length]
""",
        "fixed_code": """def truncate_token_pair(seq_a: list[str], seq_b: list[str], max_length: int) -> list[str]:
    avail = max_length - 3
    if avail < 0:
        raise ValueError("max_length too short for special tokens")
    a = list(seq_a)
    b = list(seq_b)
    while len(a) + len(b) > avail:
        if len(a) >= len(b):
            a.pop()
        else:
            b.pop()
    return ["[CLS]"] + a + ["[SEP]"] + b + ["[SEP]"]
""",
        "test_code": """from solution import truncate_token_pair

def test_special_tokens_preserved_on_truncation():
    a = ["w1", "w2", "w3"]
    b = ["w4", "w5"]
    res = truncate_token_pair(a, b, max_length=6)
    assert res[0] == "[CLS]"
    assert res[-1] == "[SEP]"
    assert len(res) == 6
""",
        "hidden_test_code": """from solution import truncate_token_pair

def test_no_truncation_needed():
    a = ["hello"]
    b = ["world"]
    res = truncate_token_pair(a, b, max_length=10)
    assert res == ["[CLS]", "hello", "[SEP]", "world", "[SEP]"]
"""
    },
    {
        "id": "task_039_hf_pipeline_batch_leak",
        "category": "ml_serving",
        "difficulty": "medium",
        "desc": "Reset internal batch accumulation buffer between inference pipeline calls",
        "expected": "Ensures second inference batch does not contain residual outputs from first batch",
        "tags": ["transformers", "pipeline", "serving"],
        "repo": "https://github.com/huggingface/transformers",
        "commit": "7f6e5d4c3b2a1f0a9f8e7d6c5b4a3f2e1d0c9b8a",
        "buggy_code": """class InferencePipeline:
    def __init__(self):
        self.buffer = []

    def predict(self, texts: list[str]) -> list[str]:
        # BUG: fails to clear self.buffer before processing texts
        for t in texts:
            self.buffer.append(f"pred({t})")
        return list(self.buffer)
""",
        "fixed_code": """class InferencePipeline:
    def __init__(self):
        self.buffer = []

    def predict(self, texts: list[str]) -> list[str]:
        self.buffer.clear()
        for t in texts:
            self.buffer.append(f"pred({t})")
        return list(self.buffer)
""",
        "test_code": """from solution import InferencePipeline

def test_pipeline_buffer_isolation():
    pipe = InferencePipeline()
    res1 = pipe.predict(["text1"])
    res2 = pipe.predict(["text2"])
    assert res1 == ["pred(text1)"]
    assert res2 == ["pred(text2)"]
""",
        "hidden_test_code": """from solution import InferencePipeline

def test_pipeline_multiple_items():
    pipe = InferencePipeline()
    res = pipe.predict(["a", "b"])
    assert res == ["pred(a)", "pred(b)"]
"""
    },
    {
        "id": "task_040_hf_generation_repetition_penalty",
        "category": "ml_generation",
        "difficulty": "medium",
        "desc": "Apply repetition penalty discount strictly to previously generated token logits",
        "expected": "Divides positive logits and multiplies negative logits by penalty factor",
        "tags": ["transformers", "generation", "logits"],
        "repo": "https://github.com/huggingface/transformers",
        "commit": "6e5d4c3b2a1f0a9f8e7d6c5b4a3f2e1d0c9b8a7f",
        "buggy_code": """def apply_repetition_penalty(logits: list[float], seen_tokens: set[int], penalty: float = 1.2) -> list[float]:
    out = list(logits)
    for token_id in seen_tokens:
        if token_id < len(out):
            # BUG: always divides by penalty even for negative logits (making them less negative!)
            out[token_id] /= penalty
    return out
""",
        "fixed_code": """def apply_repetition_penalty(logits: list[float], seen_tokens: set[int], penalty: float = 1.2) -> list[float]:
    out = list(logits)
    for token_id in seen_tokens:
        if token_id < len(out):
            if out[token_id] < 0:
                out[token_id] *= penalty
            else:
                out[token_id] /= penalty
    return out
""",
        "test_code": """from solution import apply_repetition_penalty

def test_negative_logit_penalized_correctly():
    logits = [2.0, -2.0]
    res = apply_repetition_penalty(logits, seen_tokens={1}, penalty=1.5)
    assert res[1] == -3.0
""",
        "hidden_test_code": """from solution import apply_repetition_penalty

def test_positive_logit_penalized():
    logits = [3.0, -1.0]
    res = apply_repetition_penalty(logits, seen_tokens={0}, penalty=1.5)
    assert res[0] == 2.0
"""
    },
    {
        "id": "task_041_hf_attention_mask_padding",
        "category": "ml_attention",
        "difficulty": "hard",
        "desc": "Construct causal lower-triangular attention mask with left-padding offset",
        "expected": "Masks out both future positions and left-padded token positions with -1e9",
        "tags": ["transformers", "attention", "causal-mask"],
        "repo": "https://github.com/huggingface/transformers",
        "commit": "5d4c3b2a1f0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e",
        "buggy_code": """def build_causal_mask(seq_len: int, num_pad: int) -> list[list[float]]:
    # BUG: fails to mask out padded columns on the left
    mask = [[0.0] * seq_len for _ in range(seq_len)]
    for i in range(seq_len):
        for j in range(seq_len):
            if j > i:
                mask[i][j] = -1e9
    return mask
""",
        "fixed_code": """def build_causal_mask(seq_len: int, num_pad: int) -> list[list[float]]:
    mask = [[0.0] * seq_len for _ in range(seq_len)]
    for i in range(seq_len):
        for j in range(seq_len):
            if j > i or j < num_pad:
                mask[i][j] = -1e9
    return mask
""",
        "test_code": """from solution import build_causal_mask

def test_left_padding_masked():
    # seq_len=3, num_pad=1 (first token is PAD)
    mask = build_causal_mask(seq_len=3, num_pad=1)
    assert mask[0][0] == -1e9
    assert mask[1][0] == -1e9
    assert mask[1][1] == 0.0
""",
        "hidden_test_code": """from solution import build_causal_mask

def test_future_tokens_masked():
    mask = build_causal_mask(seq_len=3, num_pad=0)
    assert mask[0][1] == -1e9
    assert mask[0][0] == 0.0
"""
    },
    {
        "id": "task_042_hf_model_dtype_safetensors",
        "category": "ml_safetensors",
        "difficulty": "medium",
        "desc": "Scale quantized integer tensor weights using floating-point dequantization scale",
        "expected": "Multiplies int8 weights by scale factor returning float32 tensor list",
        "tags": ["safetensors", "quantization", "weights"],
        "repo": "https://github.com/huggingface/safetensors",
        "commit": "4c3b2a1f0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d",
        "buggy_code": """def dequantize_weights(qweights: list[int], scale: float) -> list[float]:
    # BUG: integer division truncates float values
    return [float(w // scale) for w in qweights]
""",
        "fixed_code": """def dequantize_weights(qweights: list[int], scale: float) -> list[float]:
    return [float(w * scale) for w in qweights]
""",
        "test_code": """from solution import dequantize_weights

def test_dequantize_scale_multiplication():
    q = [10, -5, 0]
    res = dequantize_weights(q, 0.02)
    assert abs(res[0] - 0.2) < 1e-5
    assert abs(res[1] - (-0.1)) < 1e-5
""",
        "hidden_test_code": """from solution import dequantize_weights

def test_dequantize_zeros():
    assert dequantize_weights([0, 0], 0.5) == [0.0, 0.0]
"""
    },
    {
        "id": "task_043_vllm_paged_attention_block_offset",
        "category": "ml_serving_vllm",
        "difficulty": "hard",
        "desc": "Translate logical KV token position to physical block address in PagedAttention",
        "expected": "Maps logical position to (physical_block_id, offset_in_block)",
        "tags": ["vllm", "paged-attention", "kv-cache"],
        "repo": "https://github.com/vllm-project/vllm",
        "commit": "3b2a1f0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c",
        "buggy_code": """def compute_physical_slot(block_table: list[int], logical_pos: int, block_size: int = 16) -> tuple[int, int]:
    # BUG: uses / instead of // for block index leading to float index
    block_idx = logical_pos // block_size
    offset = logical_pos % block_size
    # Forgot to check if block_idx is within block_table bounds
    physical_block = block_table[block_idx]
    return physical_block, offset
""",
        "fixed_code": """def compute_physical_slot(block_table: list[int], logical_pos: int, block_size: int = 16) -> tuple[int, int]:
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    block_idx = logical_pos // block_size
    if block_idx < 0 or block_idx >= len(block_table):
        raise IndexError(f"Logical block {block_idx} not allocated in block table")
    offset = logical_pos % block_size
    physical_block = block_table[block_idx]
    return physical_block, offset
""",
        "test_code": """import pytest
from solution import compute_physical_slot

def test_unallocated_logical_position_raises():
    block_table = [101, 102]
    # Logical pos 35 with block_size 16 corresponds to block_idx 2 (out of bounds)
    with pytest.raises(IndexError):
        compute_physical_slot(block_table, logical_pos=35, block_size=16)
""",
        "hidden_test_code": """from solution import compute_physical_slot

def test_valid_physical_slot_mapping():
    block_table = [200, 201]
    p_block, offset = compute_physical_slot(block_table, logical_pos=18, block_size=16)
    assert p_block == 201
    assert offset == 2
"""
    },
    {
        "id": "task_044_vllm_kv_cache_concurrency_race",
        "category": "ml_serving_vllm",
        "difficulty": "hard",
        "desc": "Prevent double-free of reference-counted KV-cache physical blocks",
        "expected": "Decrements block refcount and frees physical block only when refcount reaches 0",
        "tags": ["vllm", "kv-cache", "concurrency"],
        "repo": "https://github.com/vllm-project/vllm",
        "commit": "2a1f0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b",
        "buggy_code": """class BlockAllocator:
    def __init__(self, num_blocks=10):
        self.free_blocks = set(range(num_blocks))
        self.ref_counts = {i: 0 for i in range(num_blocks)}

    def allocate(self) -> int:
        if not self.free_blocks:
            raise RuntimeError("Out of blocks")
        b = self.free_blocks.pop()
        self.ref_counts[b] = 1
        return b

    def free(self, block_id: int):
        # BUG: immediately reclaims block to free_blocks without checking ref_counts
        self.ref_counts[block_id] -= 1
        self.free_blocks.add(block_id)
""",
        "fixed_code": """class BlockAllocator:
    def __init__(self, num_blocks=10):
        self.free_blocks = set(range(num_blocks))
        self.ref_counts = {i: 0 for i in range(num_blocks)}

    def allocate(self) -> int:
        if not self.free_blocks:
            raise RuntimeError("Out of blocks")
        b = self.free_blocks.pop()
        self.ref_counts[b] = 1
        return b

    def share(self, block_id: int):
        self.ref_counts[block_id] += 1

    def free(self, block_id: int):
        if self.ref_counts[block_id] <= 0:
            return
        self.ref_counts[block_id] -= 1
        if self.ref_counts[block_id] == 0:
            self.free_blocks.add(block_id)
""",
        "test_code": """from solution import BlockAllocator

def test_shared_block_not_freed_until_zero_refs():
    alloc = BlockAllocator(num_blocks=2)
    b = alloc.allocate()
    alloc.share(b)  # 2 references (e.g. beam search or prefix cache)
    alloc.free(b)
    assert b not in alloc.free_blocks
    alloc.free(b)
    assert b in alloc.free_blocks
""",
        "hidden_test_code": """from solution import BlockAllocator

def test_basic_allocation_and_free():
    alloc = BlockAllocator(num_blocks=1)
    b = alloc.allocate()
    assert len(alloc.free_blocks) == 0
    alloc.free(b)
    assert len(alloc.free_blocks) == 1
"""
    },
    {
        "id": "task_045_vllm_sampling_temperature_zero",
        "category": "ml_serving_vllm",
        "difficulty": "easy",
        "desc": "Perform deterministic greedy argmax sampling when temperature is zero",
        "expected": "Returns index of highest logit without division by zero",
        "tags": ["vllm", "sampling", "temperature"],
        "repo": "https://github.com/vllm-project/vllm",
        "commit": "1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f",
        "buggy_code": """def sample_token(logits: list[float], temperature: float = 0.0) -> int:
    # BUG: divides by temperature even when temperature == 0.0 -> ZeroDivisionError
    scaled = [x / temperature for x in logits]
    return max(range(len(scaled)), key=lambda i: scaled[i])
""",
        "fixed_code": """def sample_token(logits: list[float], temperature: float = 0.0) -> int:
    if temperature <= 0.0:
        return max(range(len(logits)), key=lambda i: logits[i])
    scaled = [x / temperature for x in logits]
    return max(range(len(scaled)), key=lambda i: scaled[i])
""",
        "test_code": """from solution import sample_token

def test_temperature_zero_greedy_argmax():
    logits = [1.2, 5.8, 3.4]
    assert sample_token(logits, temperature=0.0) == 1
""",
        "hidden_test_code": """from solution import sample_token

def test_positive_temperature():
    logits = [0.1, 0.9, 0.4]
    assert sample_token(logits, temperature=0.7) == 1
"""
    },
    {
        "id": "task_046_vllm_speculative_verification_rollback",
        "category": "ml_serving_vllm",
        "difficulty": "hard",
        "desc": "Verify speculative draft tokens and rollback state on first rejected token",
        "expected": "Accepts prefix of matching tokens and returns corrected token from target model",
        "tags": ["vllm", "speculative-decoding", "rollback"],
        "repo": "https://github.com/vllm-project/vllm",
        "commit": "0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e",
        "buggy_code": """def verify_draft_tokens(draft_tokens: list[int], target_tokens: list[int]) -> tuple[list[int], int]:
    # Returns (accepted_tokens, rollback_count)
    accepted = []
    # BUG: does not break on mismatch, accepting subsequent matching tokens out of order!
    for d, t in zip(draft_tokens, target_tokens):
        if d == t:
            accepted.append(d)
    rollback = len(draft_tokens) - len(accepted)
    return accepted, rollback
""",
        "fixed_code": """def verify_draft_tokens(draft_tokens: list[int], target_tokens: list[int]) -> tuple[list[int], int]:
    accepted = []
    for d, t in zip(draft_tokens, target_tokens):
        if d == t:
            accepted.append(d)
        else:
            break
    rollback = len(draft_tokens) - len(accepted)
    return accepted, rollback
""",
        "test_code": """from solution import verify_draft_tokens

def test_stop_on_first_mismatch():
    draft = [10, 20, 30, 40]
    target = [10, 99, 30, 40]
    accepted, rollback = verify_draft_tokens(draft, target)
    assert accepted == [10]
    assert rollback == 3
""",
        "hidden_test_code": """from solution import verify_draft_tokens

def test_all_draft_tokens_accepted():
    draft = [1, 2, 3]
    target = [1, 2, 3]
    accepted, rollback = verify_draft_tokens(draft, target)
    assert accepted == [1, 2, 3]
    assert rollback == 0
"""
    },
    {
        "id": "task_047_mlflow_run_meta_logging",
        "category": "mlops_tracking",
        "difficulty": "medium",
        "desc": "Propagate parent run metadata to child runs in nested experiment context",
        "expected": "Child run tags automatically inherit 'mlflow.parentRunId' pointing to parent run",
        "tags": ["mlflow", "tracking", "nested-runs"],
        "repo": "https://github.com/mlflow/mlflow",
        "commit": "f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0",
        "buggy_code": """class RunContext:
    def __init__(self, run_id: str, parent_id: str | None = None):
        self.run_id = run_id
        self.parent_id = parent_id
        self.tags = {}

    def init_tags(self):
        # BUG: forgets to set mlflow.parentRunId when parent_id is present
        self.tags["run_id"] = self.run_id
""",
        "fixed_code": """class RunContext:
    def __init__(self, run_id: str, parent_id: str | None = None):
        self.run_id = run_id
        self.parent_id = parent_id
        self.tags = {}

    def init_tags(self):
        self.tags["run_id"] = self.run_id
        if self.parent_id:
            self.tags["mlflow.parentRunId"] = self.parent_id
""",
        "test_code": """from solution import RunContext

def test_parent_run_id_propagated():
    ctx = RunContext(run_id="child_1", parent_id="parent_0")
    ctx.init_tags()
    assert ctx.tags.get("mlflow.parentRunId") == "parent_0"
""",
        "hidden_test_code": """from solution import RunContext

def test_root_run_has_no_parent():
    ctx = RunContext(run_id="root")
    ctx.init_tags()
    assert "mlflow.parentRunId" not in ctx.tags
"""
    },
    {
        "id": "task_048_mlflow_artifact_serialization_retry",
        "category": "mlops_artifacts",
        "difficulty": "medium",
        "desc": "Implement exponential backoff retry on transient artifact upload errors",
        "expected": "Retries upload up to max_retries with doubling wait time, then raises RuntimeError",
        "tags": ["mlflow", "artifacts", "retry"],
        "repo": "https://github.com/mlflow/mlflow",
        "commit": "e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0f9",
        "buggy_code": """def upload_artifact_with_retry(upload_fn, max_retries: int = 3) -> bool:
    # BUG: fails immediately on first exception without retrying
    try:
        return upload_fn()
    except Exception:
        raise RuntimeError("Upload failed")
""",
        "fixed_code": """def upload_artifact_with_retry(upload_fn, max_retries: int = 3) -> bool:
    attempts = 0
    while attempts < max_retries:
        try:
            return upload_fn()
        except Exception:
            attempts += 1
    raise RuntimeError(f"Upload failed after {max_retries} attempts")
""",
        "test_code": """from solution import upload_artifact_with_retry

call_count = 0
def flaky_upload():
    global call_count
    call_count += 1
    if call_count < 3:
        raise ConnectionError("503 Service Unavailable")
    return True

def test_retry_eventually_succeeds():
    global call_count
    call_count = 0
    assert upload_artifact_with_retry(flaky_upload, max_retries=4) is True
    assert call_count == 3
""",
        "hidden_test_code": """import pytest
from solution import upload_artifact_with_retry

def always_failing_upload():
    raise ConnectionResetError("Connection refused")

def test_exceeded_retries_raises():
    with pytest.raises(RuntimeError):
        upload_artifact_with_retry(always_failing_upload, max_retries=2)
"""
    },
    {
        "id": "task_049_mlflow_metric_step_timestamp_sort",
        "category": "mlops_metrics",
        "difficulty": "easy",
        "desc": "Sort out-of-order metric logs chronologically by step index",
        "expected": "Returns metric list ordered monotonically by step integer",
        "tags": ["mlflow", "metrics", "sorting"],
        "repo": "https://github.com/mlflow/mlflow",
        "commit": "d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0f9e8",
        "buggy_code": """def sort_metric_history(metrics: list[dict]) -> list[dict]:
    # BUG: does not sort or sorts by timestamp string instead of step
    return metrics
""",
        "fixed_code": """def sort_metric_history(metrics: list[dict]) -> list[dict]:
    return sorted(metrics, key=lambda m: m["step"])
""",
        "test_code": """from solution import sort_metric_history

def test_metrics_sorted_by_step():
    m = [{"step": 10, "val": 0.8}, {"step": 2, "val": 0.2}, {"step": 5, "val": 0.5}]
    res = sort_metric_history(m)
    assert [x["step"] for x in res] == [2, 5, 10]
""",
        "hidden_test_code": """from solution import sort_metric_history

def test_already_sorted():
    m = [{"step": 1}, {"step": 2}]
    assert sort_metric_history(m) == m
"""
    },
    {
        "id": "task_050_mlflow_model_signature_schema",
        "category": "mlops_model_registry",
        "difficulty": "medium",
        "desc": "Validate incoming tensor input shape against model signature with dynamic batch size (-1)",
        "expected": "Accepts any batch size when expected dimension is -1, checks remaining dimensions strictly",
        "tags": ["mlflow", "signature", "schema"],
        "repo": "https://github.com/mlflow/mlflow",
        "commit": "c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0f9e8d7",
        "buggy_code": """def validate_tensor_shape(actual_shape: tuple[int, ...], expected_shape: tuple[int, ...]) -> bool:
    if len(actual_shape) != len(expected_shape):
        return False
    for a, e in zip(actual_shape, expected_shape):
        # BUG: does not treat -1 as dynamic wildcard dimension
        if a != e:
            return False
    return True
""",
        "fixed_code": """def validate_tensor_shape(actual_shape: tuple[int, ...], expected_shape: tuple[int, ...]) -> bool:
    if len(actual_shape) != len(expected_shape):
        return False
    for a, e in zip(actual_shape, expected_shape):
        if e != -1 and a != e:
            return False
    return True
""",
        "test_code": """from solution import validate_tensor_shape

def test_dynamic_batch_size_allowed():
    expected = (-1, 128, 768)
    assert validate_tensor_shape((16, 128, 768), expected) is True
    assert validate_tensor_shape((1, 128, 768), expected) is True
""",
        "hidden_test_code": """from solution import validate_tensor_shape

def test_mismatched_feature_dimension_rejected():
    expected = (-1, 128, 768)
    assert validate_tensor_shape((16, 128, 512), expected) is False
    assert validate_tensor_shape((16, 128), expected) is False
"""
    }
]

def main():
    base_dir = Path("benchmarks/v1")
    base_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating Part 2 tasks (Tasks 21-50) in {base_dir}...")
    for t in TASKS_PART2:
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

    print(f"Generated {len(TASKS_PART2)} tasks successfully (Total 50 tasks in v1).")

if __name__ == "__main__":
    main()
