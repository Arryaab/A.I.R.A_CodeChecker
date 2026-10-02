"""
Track 2 (Tasks 021 - 032) Exact-Signature Comprehensive Research-Grade Oracle Definitions
"""

ORACLE_DATA_TRACK2 = {
    # -------------------------------------------------------------------------
    # Task 021: NumPy Stride Tricks
    # -------------------------------------------------------------------------
    "task_021_numpy_stride_tricks": {
        "test_code": '''import pytest
from solution import compute_sliding_window_shape

def test_oracle_happy_path_standard_sliding_window():
    assert compute_sliding_window_shape(10, 3, 1) == (8, 3)
    assert compute_sliding_window_shape(10, 2, 2) == (5, 2)
    assert compute_sliding_window_shape(7, 3, 2) == (3, 3)

def test_oracle_boundary_window_equals_length():
    assert compute_sliding_window_shape(5, 5, 1) == (1, 5)

def test_oracle_boundary_window_exceeds_length():
    assert compute_sliding_window_shape(3, 5, 1) == (0, 0)

def test_oracle_boundary_invalid_window_size():
    assert compute_sliding_window_shape(10, 0, 1) == (0, 0)
    assert compute_sliding_window_shape(10, -1, 1) == (0, 0)

def test_oracle_adversarial_step_larger_than_window():
    assert compute_sliding_window_shape(10, 2, 5) == (2, 2)
''',
        "mutations": [
            {
                "id": "mutant_omit_plus_one",
                "type": "off_by_one",
                "description": "Omits +1 from sliding window count calculation",
                "code": '''def compute_sliding_window_shape(n_elements: int, window_size: int, step: int = 1) -> tuple[int, int]:
    if window_size > n_elements or window_size <= 0:
        return (0, 0)
    num_windows = (n_elements - window_size) // step
    return (num_windows, window_size)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_hardcode_window_shape",
                "description": "Hardcodes window shape",
                "code": '''def compute_sliding_window_shape(n_elements: int, window_size: int, step: int = 1) -> tuple[int, int]:
    return (8, 3)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "strided_indexing",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Calculates 1D sliding window shape (num_windows, window_size) correctly including the terminal window offset (n - window_size) // step + 1."
    },

    # -------------------------------------------------------------------------
    # Task 022: NumPy Broadcast Edge
    # -------------------------------------------------------------------------
    "task_022_numpy_broadcast_edge": {
        "test_code": '''import pytest
from solution import broadcast_shapes

def test_oracle_happy_path_unit_dimension_broadcasting():
    assert broadcast_shapes((3, 4), (3, 1)) == (3, 4)
    assert broadcast_shapes((3, 1), (3, 4)) == (3, 4)
    assert broadcast_shapes((1, 5), (2, 1)) == (2, 5)

def test_oracle_happy_path_rank_expansion():
    assert broadcast_shapes((5,), (2, 5)) == (2, 5)
    assert broadcast_shapes((2, 5), (5,)) == (2, 5)

def test_oracle_negative_incompatible_dimensions():
    with pytest.raises(ValueError):
        broadcast_shapes((3,), (4,))
    with pytest.raises(ValueError):
        broadcast_shapes((2, 3), (2, 4))

def test_oracle_boundary_identical_shapes():
    assert broadcast_shapes((2, 3, 4), (2, 3, 4)) == (2, 3, 4)
''',
        "mutations": [
            {
                "id": "mutant_omit_d2_one_branch",
                "type": "logic_gap",
                "description": "Omits handling of d2 == 1, raising false shape mismatch",
                "code": '''def broadcast_shapes(s1: tuple[int, ...], s2: tuple[int, ...]) -> tuple[int, ...]:
    n1, n2 = len(s1), len(s2)
    max_len = max(n1, n2)
    p1 = (1,) * (max_len - n1) + s1
    p2 = (1,) * (max_len - n2) + s2
    res = []
    for d1, d2 in zip(p1, p2):
        if d1 == d2:
            res.append(d1)
        elif d1 == 1:
            res.append(d2)
        else:
            raise ValueError(f"Cannot broadcast shapes {s1} and {s2}")
    return tuple(res)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_return_s1_always",
                "description": "Always returns s1",
                "code": '''def broadcast_shapes(s1: tuple[int, ...], s2: tuple[int, ...]) -> tuple[int, ...]:
    return s1
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "array_dimension_logic",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Computes multidimensional broadcasted output shape following NumPy semantics: expanding 1s against matching dimensions."
    },

    # -------------------------------------------------------------------------
    # Task 023: NumPy Dtype Overflow
    # -------------------------------------------------------------------------
    "task_023_numpy_dtype_overflow": {
        "test_code": '''import pytest
from solution import accumulate_int32, INT32_MAX, INT32_MIN

def test_oracle_happy_path_within_bounds():
    assert accumulate_int32([100, 200, 300]) == 600
    assert accumulate_int32([-100, -200, 50]) == -250

def test_oracle_negative_positive_overflow():
    with pytest.raises(OverflowError, match="32-bit integer overflow"):
        accumulate_int32([INT32_MAX, 1])

def test_oracle_negative_negative_overflow():
    with pytest.raises(OverflowError, match="32-bit integer overflow"):
        accumulate_int32([INT32_MIN, -1])

def test_oracle_boundary_exact_limits():
    assert accumulate_int32([INT32_MAX]) == INT32_MAX
    assert accumulate_int32([INT32_MIN]) == INT32_MIN
''',
        "mutations": [
            {
                "id": "mutant_omit_lower_bound_check",
                "type": "missing_boundary_check",
                "description": "Fails to check total < INT32_MIN",
                "code": '''INT32_MAX = 2**31 - 1
INT32_MIN = -2**31

def accumulate_int32(values: list[int]) -> int:
    total = 0
    for v in values:
        total += v
        if total > INT32_MAX:
            raise OverflowError("32-bit integer overflow")
    return total
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_sum_only",
                "description": "Normal sum without overflow checks",
                "code": '''INT32_MAX = 2**31 - 1
INT32_MIN = -2**31

def accumulate_int32(values: list[int]) -> int:
    return sum(values)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "integer_overflow",
            "SECURITY_SENSITIVITY": "medium",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Accumulates signed 32-bit integers and raises OverflowError if total exceeds INT32_MAX or falls below INT32_MIN."
    },

    # -------------------------------------------------------------------------
    # Task 024: NumPy Masked Array NaN
    # -------------------------------------------------------------------------
    "task_024_numpy_masked_array_nan": {
        "test_code": '''import pytest
import math
from solution import nanmean_masked

def test_oracle_happy_path_excludes_both_mask_and_nan():
    data = [1.0, float('nan'), 3.0, 5.0]
    mask = [False, False, False, True]
    # valid values: 1.0 and 3.0 (nan is skipped, 5.0 is masked)
    assert nanmean_masked(data, mask) == 2.0

def test_oracle_boundary_no_masked_no_nan():
    assert nanmean_masked([2.0, 4.0, 6.0], [False, False, False]) == 4.0

def test_oracle_boundary_all_invalid_returns_nan():
    res = nanmean_masked([float('nan'), 1.0], [False, True])
    assert math.isnan(res)

def test_oracle_adversarial_multiple_nans():
    data = [float('nan'), float('nan'), 50.0]
    mask = [False, False, False]
    assert nanmean_masked(data, mask) == 50.0
''',
        "mutations": [
            {
                "id": "mutant_omit_nan_check",
                "type": "nan_leak",
                "description": "Omits math.isnan(x) check, allowing NaNs to contaminate mean",
                "code": '''import math

def nanmean_masked(data: list[float], mask: list[bool]) -> float:
    valid_elements = []
    for x, m in zip(data, mask):
        if not m:
            valid_elements.append(x)
    if not valid_elements:
        return float('nan')
    return sum(valid_elements) / len(valid_elements)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_return_zero_always",
                "description": "Returns 0.0 always",
                "code": '''def nanmean_masked(data: list[float], mask: list[bool]) -> float:
    return 0.0
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "numeric_validation",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Computes arithmetic mean filtering out both Boolean-masked entries and IEEE-754 NaN floats, returning NaN if zero valid numbers exist."
    },

    # -------------------------------------------------------------------------
    # Task 025: NumPy Matrix Power Zero
    # -------------------------------------------------------------------------
    "task_025_numpy_matrix_power_zero": {
        "test_code": '''import pytest
from solution import matrix_power

def test_oracle_happy_path_power_zero_is_identity():
    m = [[2.0, 3.0], [4.0, 5.0]]
    expected = [[1.0, 0.0], [0.0, 1.0]]
    assert matrix_power(m, 0) == expected

def test_oracle_boundary_power_zero_3x3():
    m = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
    expected = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0]
    ]
    assert matrix_power(m, 0) == expected

def test_oracle_regression_power_one():
    m = [[2.0, 1.0], [0.0, 2.0]]
    assert matrix_power(m, 1) == m
''',
        "mutations": [
            {
                "id": "mutant_zero_matrix_on_power_zero",
                "type": "wrong_identity",
                "description": "Returns zero matrix when power == 0",
                "code": '''def matrix_power(matrix: list[list[float]], power: int) -> list[list[float]]:
    n = len(matrix)
    if power == 0:
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
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_return_original_on_zero",
                "description": "Returns original matrix on power 0",
                "code": '''def matrix_power(matrix: list[list[float]], power: int) -> list[list[float]]:
    return matrix
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(p * N^3)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "linear_algebra",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Computes square matrix exponentiation returning an identity matrix for power=0."
    },

    # -------------------------------------------------------------------------
    # Task 026: NumPy Clip Inplace View
    # -------------------------------------------------------------------------
    "task_026_numpy_clip_inplace_view": {
        "test_code": '''import pytest
from solution import clip_array

def test_oracle_happy_path_clipping():
    arr = [-10.0, 0.0, 5.0, 10.0, 20.0]
    res = clip_array(arr, a_min=0.0, a_max=10.0)
    assert res == [0.0, 0.0, 5.0, 10.0, 10.0]

def test_oracle_boundary_all_within_bounds():
    arr = [1.0, 2.0, 3.0]
    assert clip_array(arr, 0.0, 5.0) == [1.0, 2.0, 3.0]

def test_oracle_boundary_all_below_min():
    arr = [-5.0, -10.0]
    assert clip_array(arr, 0.0, 10.0) == [0.0, 0.0]
''',
        "mutations": [
            {
                "id": "mutant_invert_clip_conditions",
                "type": "inverted_clamping",
                "description": "Clamps x > a_max to a_min and x < a_min to a_max",
                "code": '''def clip_array(arr: list[float], a_min: float, a_max: float) -> list[float]:
    return [a_min if x > a_max else a_max if x < a_min else x for x in arr]
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_return_arr_unchanged",
                "description": "Returns array without clipping",
                "code": '''def clip_array(arr: list[float], a_min: float, a_max: float) -> list[float]:
    return list(arr)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "numeric_clamping",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Clips numerical array values to closed interval [a_min, a_max]."
    },

    # -------------------------------------------------------------------------
    # Task 027: Pandas MultiIndex Alignment
    # -------------------------------------------------------------------------
    "task_027_pandas_multiindex_alignment": {
        "test_code": '''import pytest
from solution import align_multiindex_data

def test_oracle_happy_path_outer_join():
    d1 = {("A", 1): 10}
    d2 = {("B", 2): 20}
    res = align_multiindex_data(d1, d2)
    assert res == {("A", 1): 10, ("B", 2): 20}

def test_oracle_happy_path_sum_overlapping():
    d1 = {("A", 1): 5, ("A", 2): 10}
    d2 = {("A", 2): 15, ("C", 1): 20}
    res = align_multiindex_data(d1, d2)
    assert res[("A", 1)] == 5
    assert res[("A", 2)] == 25
    assert res[("C", 1)] == 20

def test_oracle_boundary_one_empty():
    d1 = {("X", 1): 100}
    assert align_multiindex_data(d1, {}) == {("X", 1): 100}
''',
        "mutations": [
            {
                "id": "mutant_df1_keys_only",
                "type": "inner_join_defect",
                "description": "Only iterates over df1 keys, dropping df2-only keys",
                "code": '''def align_multiindex_data(df1: dict, df2: dict) -> dict:
    aligned = {}
    for (k1, k2), v1 in df1.items():
        v2 = df2.get((k1, k2), 0)
        aligned[(k1, k2)] = v1 + v2
    return aligned
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_merge_dict_only",
                "description": "Overwrites overlapping keys instead of adding values",
                "code": '''def align_multiindex_data(df1: dict, df2: dict) -> dict:
    res = dict(df1)
    res.update(df2)
    return res
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N log N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "relational_alignment",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Aligns two MultiIndex dictionaries via full outer join, summing values for shared keys."
    },

    # -------------------------------------------------------------------------
    # Task 028: Pandas Datetime TZ Convert
    # -------------------------------------------------------------------------
    "task_028_pandas_datetime_tz_convert": {
        "test_code": '''import pytest
from datetime import datetime
from solution import convert_tz_utc

def test_oracle_happy_path_day_rollover():
    dt = datetime(2026, 9, 27, 23, 0)
    res = convert_tz_utc(dt, 2)
    assert res == datetime(2026, 9, 28, 1, 0)

def test_oracle_happy_path_negative_offset():
    dt = datetime(2026, 9, 28, 1, 0)
    res = convert_tz_utc(dt, -2)
    assert res == datetime(2026, 9, 27, 23, 0)

def test_oracle_boundary_zero_offset():
    dt = datetime(2026, 5, 1, 12, 0)
    assert convert_tz_utc(dt, 0) == dt
''',
        "mutations": [
            {
                "id": "mutant_modulo_hour_replace",
                "type": "rollover_truncation",
                "description": "Uses hour modulo arithmetic with replace(), dropping calendar day transitions",
                "code": '''from datetime import datetime

def convert_tz_utc(dt: datetime, offset_hours: int) -> datetime:
    new_hour = (dt.hour + offset_hours) % 24
    return dt.replace(hour=new_hour)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_return_dt_unchanged",
                "description": "Returns original datetime",
                "code": '''def convert_tz_utc(dt: datetime, offset_hours: int) -> datetime:
    return dt
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "datetime_arithmetic",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Converts timestamps across timezone offsets using full timedelta addition to preserve calendar day transitions."
    },

    # -------------------------------------------------------------------------
    # Task 029: Pandas Rolling Min Periods
    # -------------------------------------------------------------------------
    "task_029_pandas_rolling_min_periods": {
        "test_code": '''import pytest
from solution import rolling_mean

def test_oracle_happy_path_requires_min_periods():
    s = [10.0, None, 20.0, 30.0]
    res = rolling_mean(s, window=3, min_periods=2)
    assert res[0] is None
    assert res[1] is None
    assert res[2] == 15.0
    assert res[3] == 25.0

def test_oracle_happy_path_two_valid():
    s = [10.0, 20.0, 30.0]
    res = rolling_mean(s, window=2, min_periods=2)
    assert res == [None, 15.0, 25.0]

def test_oracle_boundary_all_valid():
    s = [2.0, 4.0]
    res = rolling_mean(s, window=2, min_periods=1)
    assert res == [2.0, 3.0]
''',
        "mutations": [
            {
                "id": "mutant_check_sub_length_instead_of_valid",
                "type": "null_accounting_error",
                "description": "Checks window size len(sub) rather than non-null valid observation count",
                "code": '''def rolling_mean(series: list[float | None], window: int, min_periods: int) -> list[float | None]:
    result = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        sub = series[start:i+1]
        valid = [x for x in sub if x is not None]
        if len(sub) >= min_periods and valid:
            result.append(sum(valid) / len(valid))
        else:
            result.append(None)
    return result
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_all_none",
                "description": "Always returns None",
                "code": '''def rolling_mean(series: list[float | None], window: int, min_periods: int) -> list[float | None]:
    return [None] * len(series)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N * W)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "windowing_semantics",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Computes rolling window mean requiring at least min_periods non-null observations in the active slice."
    },

    # -------------------------------------------------------------------------
    # Task 030: SciPy Sparse CSR Slice
    # -------------------------------------------------------------------------
    "task_030_scipy_sparse_csr_slice": {
        "test_code": '''import pytest
from solution import csr_row_slice

def test_oracle_happy_path_row_slice():
    indptr = [0, 2, 4]
    indices = [0, 1, 0, 1]
    data = [1.0, 2.0, 3.0, 4.0]
    idx, d = csr_row_slice(indptr, indices, data, row=0)
    assert idx == [0, 1] and d == [1.0, 2.0]

def test_oracle_negative_negative_row_raises():
    indptr = [0, 2, 4]
    indices = [0, 1, 0, 1]
    data = [1.0, 2.0, 3.0, 4.0]
    with pytest.raises(IndexError):
        csr_row_slice(indptr, indices, data, row=-1)

def test_oracle_negative_row_out_of_bounds():
    indptr = [0, 2, 4]
    indices = [0, 1, 0, 1]
    data = [1.0, 2.0, 3.0, 4.0]
    with pytest.raises(IndexError):
        csr_row_slice(indptr, indices, data, row=2)
''',
        "mutations": [
            {
                "id": "mutant_permit_negative_index",
                "type": "bounds_check_missing",
                "description": "Allows Python negative list indexing to corrupt CSR pointer lookup",
                "code": '''def csr_row_slice(indptr: list[int], indices: list[int], data: list[float], row: int):
    start = indptr[row]
    end = indptr[row + 1]
    return indices[start:end], data[start:end]
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_empty_slice",
                "description": "Always returns empty slice",
                "code": '''def csr_row_slice(indptr: list[int], indices: list[int], data: list[float], row: int):
    return [], []
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "sparse_matrix_indexing",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Extracts CSR row slices using contiguous index pointers while explicitly validating row bounds [0, len(indptr)-2] and raising IndexError on negative indices."
    },

    # -------------------------------------------------------------------------
    # Task 031: SciPy Optim Bounds Clamping
    # -------------------------------------------------------------------------
    "task_031_scipy_optim_bounds_clamping": {
        "test_code": '''import pytest
from solution import project_box_bounds

def test_oracle_happy_path_clamping():
    x = [-2.0, 1.5, 5.0]
    bounds = [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)]
    assert project_box_bounds(x, bounds) == [0.0, 1.5, 3.0]

def test_oracle_boundary_exact_limits():
    x = [0.0, 2.0]
    bounds = [(0.0, 2.0), (0.0, 2.0)]
    assert project_box_bounds(x, bounds) == [0.0, 2.0]

def test_oracle_boundary_all_interior():
    x = [1.0, 1.0]
    bounds = [(0.0, 5.0), (0.0, 5.0)]
    assert project_box_bounds(x, bounds) == [1.0, 1.0]
''',
        "mutations": [
            {
                "id": "mutant_invert_min_max_clamping",
                "type": "inverted_clamping",
                "description": "Inverts min and max nesting: min(l, max(u, val))",
                "code": '''def project_box_bounds(x: list[float], bounds: list[tuple[float, float]]) -> list[float]:
    projected = []
    for val, (l, u) in zip(x, bounds):
        projected.append(min(l, max(u, val)))
    return projected
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_passthrough",
                "description": "Returns x without clamping",
                "code": '''def project_box_bounds(x: list[float], bounds: list[tuple[float, float]]) -> list[float]:
    return list(x)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "projection_operator",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Projects optimization vectors onto multidimensional box constraints [lower, upper] ensuring projected components satisfy lower <= x <= upper."
    },

    # -------------------------------------------------------------------------
    # Task 032: SciPy Distance Metric Symmetry
    # -------------------------------------------------------------------------
    "task_032_scipy_distance_metric_symmetry": {
        "test_code": '''import pytest
from solution import pairwise_euclidean

def test_oracle_happy_path_symmetry():
    pts = [(0.0, 0.0), (3.0, 4.0)]
    d = pairwise_euclidean(pts)
    assert d[0][1] == 5.0
    assert d[1][0] == 5.0
    assert d[0][0] == 0.0

def test_oracle_happy_path_3_points():
    pts = [(0.0, 0.0), (1.0, 0.0), (0.0, 2.0)]
    d = pairwise_euclidean(pts)
    assert d[0][1] == 1.0 and d[1][0] == 1.0
    assert d[0][2] == 2.0 and d[2][0] == 2.0

def test_oracle_boundary_single_point():
    pts = [(10.0, 10.0)]
    assert pairwise_euclidean(pts) == [[0.0]]
''',
        "mutations": [
            {
                "id": "mutant_omit_mirror_assignment",
                "type": "symmetry_break",
                "description": "Forgets to assign dist[j][i] = d, leaving lower triangle as zero",
                "code": '''import math

def pairwise_euclidean(points: list[tuple[float, float]]) -> list[list[float]]:
    n = len(points)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            d = math.sqrt((points[i][0] - points[j][0])**2 + (points[i][1] - points[j][1])**2)
            dist[i][j] = d
    return dist
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_all_zeros",
                "description": "Returns zero matrix",
                "code": '''def pairwise_euclidean(points: list[tuple[float, float]]) -> list[list[float]]:
    n = len(points)
    return [[0.0] * n for _ in range(n)]
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N^2)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "matrix_properties",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Computes Euclidean distance matrix guaranteeing strict matrix symmetry D[i][j] == D[j][i] and zero self-distances on the main diagonal."
    }
}
