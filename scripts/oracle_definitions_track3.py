"""
Track 3 (Tasks 033 - 050) Exact-Signature Comprehensive Research-Grade Oracle Definitions
"""

ORACLE_DATA_TRACK3 = {
    # -------------------------------------------------------------------------
    # Task 033: PyTorch Graph Detachment
    # -------------------------------------------------------------------------
    "task_033_pytorch_graph_detachment": {
        "test_code": '''import pytest
from solution import Node, square_node, backward

def test_oracle_happy_path_backward_gradient():
    x = Node(3.0)
    y = square_node(x)
    backward(y)
    assert x.grad == 6.0

def test_oracle_happy_path_chain():
    x = Node(2.0)
    y = square_node(x)
    z = square_node(y)
    backward(z)
    assert z.val == 16.0
    assert x.grad == 32.0

def test_oracle_boundary_zero():
    x = Node(0.0)
    y = square_node(x)
    backward(y)
    assert x.grad == 0.0
''',
        "mutations": [
            {
                "id": "mutant_detached_node",
                "type": "graph_disconnection",
                "description": "Returns Node without connecting prev linkage",
                "code": '''class Node:
    def __init__(self, val, grad=0.0, prev=None):
        self.val = val
        self.grad = grad
        self.prev = prev or []

def square_node(x: Node) -> Node:
    return Node(x.val ** 2, prev=[])

def backward(out: Node):
    out.grad = 1.0
    queue = [out]
    while queue:
        curr = queue.pop(0)
        for p in curr.prev:
            p.grad += curr.grad * (2 * p.val)
            queue.append(p)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_set_grad_directly",
                "description": "Sets grad directly in square_node without backward traversal",
                "code": '''class Node:
    def __init__(self, val, grad=0.0, prev=None):
        self.val = val
        self.grad = grad
        self.prev = prev or []

def square_node(x: Node) -> Node:
    x.grad = 2 * x.val
    return Node(x.val ** 2, prev=[])

def backward(out: Node):
    out.grad = 1.0
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(V + E)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "autograd_graph",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Preserves automatic differentiation computation graph connectivity across square_node operations ensuring gradient backpropagation computes 2*x."
    },

    # -------------------------------------------------------------------------
    # Task 034: PyTorch Device Sync Barrier
    # -------------------------------------------------------------------------
    "task_034_pytorch_device_sync_barrier": {
        "test_code": '''import pytest
from solution import StreamManager

def test_oracle_happy_path_synchronize_drains():
    mgr = StreamManager()
    mgr.record_event("matmul")
    mgr.record_event("conv")
    assert mgr.is_idle() is False
    mgr.synchronize()
    assert mgr.is_idle() is True
    assert mgr.pending_tasks == []

def test_oracle_boundary_empty_sync():
    mgr = StreamManager()
    mgr.synchronize()
    assert mgr.is_idle() is True

def test_oracle_repeated_events():
    mgr = StreamManager()
    mgr.record_event("t1")
    mgr.synchronize()
    assert mgr.is_idle() is True
    mgr.record_event("t2")
    assert mgr.is_idle() is False
''',
        "mutations": [
            {
                "id": "mutant_noop_sync",
                "type": "missing_operation",
                "description": "Leaves pending_tasks populated on synchronize()",
                "code": '''class StreamManager:
    def __init__(self):
        self.pending_tasks = []
    def record_event(self, task_name):
        self.pending_tasks.append(task_name)
    def synchronize(self):
        pass
    def is_idle(self) -> bool:
        return len(self.pending_tasks) == 0
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_always_idle",
                "description": "Always returns True for is_idle",
                "code": '''class StreamManager:
    def __init__(self):
        self.pending_tasks = []
    def record_event(self, task_name):
        pass
    def synchronize(self):
        pass
    def is_idle(self) -> bool:
        return True
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "barrier_synchronization",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "StreamManager drains pending asynchronous tasks on synchronize() and reports idle state accurately."
    },

    # -------------------------------------------------------------------------
    # Task 035: PyTorch BatchNorm Eval Mode
    # -------------------------------------------------------------------------
    "task_035_pytorch_batch_norm_eval_mode": {
        "test_code": '''import pytest
from solution import BatchNorm1D

def test_oracle_happy_path_train_mode_updates():
    bn = BatchNorm1D(momentum=0.5)
    bn.running_mean = 0.0
    bn.training = True
    res = bn.forward(10.0)
    assert res == 5.0
    assert bn.running_mean == 5.0

def test_oracle_negative_eval_mode_freezes_running_mean():
    bn = BatchNorm1D(momentum=0.5)
    bn.running_mean = 10.0
    bn.training = False
    res = bn.forward(100.0)
    assert res == 10.0
    assert bn.running_mean == 10.0

def test_oracle_boundary_zero_momentum():
    bn = BatchNorm1D(momentum=0.0)
    bn.running_mean = 4.0
    bn.training = True
    assert bn.forward(20.0) == 4.0
''',
        "mutations": [
            {
                "id": "mutant_unconditional_update",
                "type": "mode_gate_missing",
                "description": "Updates running_mean unconditionally even in eval mode",
                "code": '''class BatchNorm1D:
    def __init__(self, momentum=0.1):
        self.running_mean = 0.0
        self.momentum = momentum
        self.training = True
    def forward(self, batch_mean: float):
        self.running_mean = (1 - self.momentum) * self.running_mean + self.momentum * batch_mean
        return self.running_mean
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_never_update",
                "description": "Never updates running_mean",
                "code": '''class BatchNorm1D:
    def __init__(self, momentum=0.1):
        self.running_mean = 0.0
        self.momentum = momentum
        self.training = True
    def forward(self, batch_mean: float):
        return self.running_mean
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "eval_vs_train_state",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "BatchNorm1D updates running statistics strictly while training is True, preserving running mean in eval mode."
    },

    # -------------------------------------------------------------------------
    # Task 036: PyTorch Optimizer Param Group
    # -------------------------------------------------------------------------
    "task_036_pytorch_optimizer_param_group": {
        "test_code": '''import pytest
from solution import step_lr_scheduler

def test_oracle_happy_path_all_groups_decay():
    groups = [
        {"name": "backbone", "lr": 1e-3},
        {"name": "head", "lr": 1e-2},
        {"name": "bias", "lr": 1e-1}
    ]
    step_lr_scheduler(groups, 0.1)
    assert abs(groups[0]["lr"] - 1e-4) < 1e-7
    assert abs(groups[1]["lr"] - 1e-3) < 1e-7
    assert abs(groups[2]["lr"] - 1e-2) < 1e-7

def test_oracle_boundary_empty():
    groups = []
    step_lr_scheduler(groups, 0.5)
    assert groups == []

def test_oracle_boundary_single():
    groups = [{"lr": 0.5}]
    step_lr_scheduler(groups, 0.2)
    assert abs(groups[0]["lr"] - 0.1) < 1e-7
''',
        "mutations": [
            {
                "id": "mutant_first_group_only",
                "type": "loop_omission",
                "description": "Only updates the first parameter group",
                "code": '''def step_lr_scheduler(param_groups: list[dict], decay_factor: float):
    if param_groups:
        param_groups[0]["lr"] *= decay_factor
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_set_zero",
                "description": "Sets all lrs to 0.0",
                "code": '''def step_lr_scheduler(param_groups: list[dict], decay_factor: float):
    for group in param_groups:
        group["lr"] = 0.0
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "multi_group_iteration",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Iterates through all parameter groups and scales lr by decay_factor across every group."
    },

    # -------------------------------------------------------------------------
    # Task 037: PyTorch DataLoader Worker Seed
    # -------------------------------------------------------------------------
    "task_037_pytorch_dataloader_worker_seed": {
        "test_code": '''import pytest
from solution import generate_worker_seed

def test_oracle_happy_path_workers_have_distinct_seeds():
    base = 42
    s0 = generate_worker_seed(base, worker_id=0)
    s1 = generate_worker_seed(base, worker_id=1)
    s2 = generate_worker_seed(base, worker_id=2)
    assert len({s0, s1, s2}) == 3

def test_oracle_invariant_determinism():
    assert generate_worker_seed(100, 3) == generate_worker_seed(100, 3)

def test_oracle_boundary_fits_31_bit_int():
    for w in range(10):
        s = generate_worker_seed(2**31 - 2, w)
        assert 0 <= s < 2**31 - 1
''',
        "mutations": [
            {
                "id": "mutant_ignore_worker_id",
                "type": "seed_collision",
                "description": "Returns base_seed ignoring worker_id",
                "code": '''def generate_worker_seed(base_seed: int, worker_id: int) -> int:
    return base_seed
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_return_zero",
                "description": "Always returns 0",
                "code": '''def generate_worker_seed(base_seed: int, worker_id: int) -> int:
    return 0
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "pseudorandom_seeding",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Generates independent deterministic seeds for multiprocessing DataLoader workers."
    },

    # -------------------------------------------------------------------------
    # Task 038: HF Tokenizer Truncation Overflow
    # -------------------------------------------------------------------------
    "task_038_hf_tokenizer_truncation_overflow": {
        "test_code": '''import pytest
from solution import truncate_token_pair

def test_oracle_happy_path_truncates_preserving_special():
    a = ["w1", "w2", "w3"]
    b = ["w4", "w5"]
    res = truncate_token_pair(a, b, max_length=6)
    assert res[0] == "[CLS]"
    assert res[-1] == "[SEP]"
    assert len(res) == 6

def test_oracle_boundary_no_truncation_needed():
    a = ["w1"]
    b = ["w2"]
    res = truncate_token_pair(a, b, max_length=10)
    assert res == ["[CLS]", "w1", "[SEP]", "w2", "[SEP]"]

def test_oracle_negative_max_length_too_short():
    with pytest.raises(ValueError, match="max_length too short"):
        truncate_token_pair(["a"], ["b"], max_length=2)
''',
        "mutations": [
            {
                "id": "mutant_naive_slice_drops_sep",
                "type": "token_truncation_defect",
                "description": "Slices concatenated tokens directly, dropping the trailing [SEP]",
                "code": '''def truncate_token_pair(seq_a: list[str], seq_b: list[str], max_length: int) -> list[str]:
    merged = ["[CLS]"] + seq_a + ["[SEP]"] + seq_b + ["[SEP]"]
    return merged[:max_length]
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_special_tokens_only",
                "description": "Returns special tokens only",
                "code": '''def truncate_token_pair(seq_a: list[str], seq_b: list[str], max_length: int) -> list[str]:
    return ["[CLS]", "[SEP]", "[SEP]"]
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "token_boundary",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Truncates token pairs from longer sequence preserving [CLS] and [SEP] boundary tokens."
    },

    # -------------------------------------------------------------------------
    # Task 039: HF Pipeline Batch Leak
    # -------------------------------------------------------------------------
    "task_039_hf_pipeline_batch_leak": {
        "test_code": '''import pytest
from solution import InferencePipeline

def test_oracle_happy_path_batch_isolation():
    pipe = InferencePipeline()
    res1 = pipe.predict(["text1", "text2"])
    assert res1 == ["pred(text1)", "pred(text2)"]
    res2 = pipe.predict(["text3"])
    assert res2 == ["pred(text3)"]
    assert len(pipe.buffer) == 1

def test_oracle_boundary_empty():
    pipe = InferencePipeline()
    assert pipe.predict([]) == []
    assert pipe.buffer == []

def test_oracle_interaction_multiple_invocations():
    pipe = InferencePipeline()
    for word in ["a", "b", "c"]:
        assert pipe.predict([word]) == [f"pred({word})"]
''',
        "mutations": [
            {
                "id": "mutant_omit_buffer_clear",
                "type": "buffer_leak",
                "description": "Fails to clear self.buffer before processing batch",
                "code": '''class InferencePipeline:
    def __init__(self):
        self.buffer = []
    def predict(self, texts: list[str]) -> list[str]:
        for t in texts:
            self.buffer.append(f"pred({t})")
        return list(self.buffer)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_stateless_list",
                "description": "Does not populate self.buffer at all",
                "code": '''class InferencePipeline:
    def __init__(self):
        self.buffer = []
    def predict(self, texts: list[str]) -> list[str]:
        return [f"pred({t})" for t in texts]
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "batch_state_leak",
            "SECURITY_SENSITIVITY": "medium",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Clears internal batch accumulation buffer before each inference call to prevent cross-batch contamination."
    },

    # -------------------------------------------------------------------------
    # Task 040: HF Generation Repetition Penalty
    # -------------------------------------------------------------------------
    "task_040_hf_generation_repetition_penalty": {
        "test_code": '''import pytest
from solution import apply_repetition_penalty

def test_oracle_happy_path_positive_and_negative():
    logits = [2.0, -2.0, 5.0]
    res = apply_repetition_penalty(logits, seen_tokens={0, 1}, penalty=2.0)
    assert res[0] == pytest.approx(1.0)
    assert res[1] == pytest.approx(-4.0)
    assert res[2] == pytest.approx(5.0)

def test_oracle_boundary_no_seen_tokens():
    logits = [1.0, -1.0]
    res = apply_repetition_penalty(logits, seen_tokens=set(), penalty=2.0)
    assert res == logits

def test_oracle_boundary_penalty_one():
    logits = [3.0, -3.0]
    res = apply_repetition_penalty(logits, seen_tokens={0, 1}, penalty=1.0)
    assert res == logits
''',
        "mutations": [
            {
                "id": "mutant_divide_negative_logits",
                "type": "mathematical_inversion",
                "description": "Always divides by penalty even for negative logits",
                "code": '''def apply_repetition_penalty(logits: list[float], seen_tokens: set[int], penalty: float = 1.2) -> list[float]:
    out = list(logits)
    for token_id in seen_tokens:
        if token_id < len(out):
            out[token_id] /= penalty
    return out
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_passthrough_logits",
                "description": "Returns logits without applying penalty",
                "code": '''def apply_repetition_penalty(logits: list[float], seen_tokens: set[int], penalty: float = 1.2) -> list[float]:
    return list(logits)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "logit_penalization",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Applies HuggingFace repetition penalty: dividing positive logits by penalty and multiplying negative logits by penalty."
    },

    # -------------------------------------------------------------------------
    # Task 041: HF Attention Mask Padding
    # -------------------------------------------------------------------------
    "task_041_hf_attention_mask_padding": {
        "test_code": '''import pytest
from solution import build_causal_mask

def test_oracle_happy_path_left_padded():
    mask = build_causal_mask(seq_len=3, num_pad=1)
    assert mask[0][0] == -1e9
    assert mask[1][0] == -1e9
    assert mask[1][1] == 0.0

def test_oracle_boundary_no_pad():
    mask = build_causal_mask(seq_len=2, num_pad=0)
    assert mask[0][0] == 0.0
    assert mask[0][1] == -1e9
    assert mask[1][0] == 0.0
    assert mask[1][1] == 0.0

def test_oracle_invariants_future_tokens_masked():
    mask = build_causal_mask(seq_len=4, num_pad=1)
    for i in range(4):
        for j in range(i + 1, 4):
            assert mask[i][j] == -1e9
''',
        "mutations": [
            {
                "id": "mutant_omit_pad_column_masking",
                "type": "mask_leak",
                "description": "Fails to zero out left-padded columns",
                "code": '''def build_causal_mask(seq_len: int, num_pad: int) -> list[list[float]]:
    mask = [[0.0] * seq_len for _ in range(seq_len)]
    for i in range(seq_len):
        for j in range(seq_len):
            if j > i:
                mask[i][j] = -1e9
    return mask
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_all_zeros_mask",
                "description": "Returns all-zeros mask",
                "code": '''def build_causal_mask(seq_len: int, num_pad: int) -> list[list[float]]:
    return [[0.0] * seq_len for _ in range(seq_len)]
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N^2)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "attention_masking",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Constructs causal attention mask with left-padding offset, assigning -1e9 to padded columns j < num_pad and future columns j > i."
    },

    # -------------------------------------------------------------------------
    # Task 042: HF Model Dtype SafeTensors
    # -------------------------------------------------------------------------
    "task_042_hf_model_dtype_safetensors": {
        "test_code": '''import pytest
from solution import dequantize_weights

def test_oracle_happy_path_scaling():
    q = [10, -5, 0]
    res = dequantize_weights(q, 0.02)
    assert abs(res[0] - 0.2) < 1e-5
    assert abs(res[1] - (-0.1)) < 1e-5
    assert res[2] == 0.0

def test_oracle_fractional_precision():
    q = [3]
    res = dequantize_weights(q, 0.1)
    assert abs(res[0] - 0.3) < 1e-5

def test_oracle_boundary_empty():
    assert dequantize_weights([], 0.5) == []
''',
        "mutations": [
            {
                "id": "mutant_integer_division",
                "type": "precision_truncation",
                "description": "Uses integer division w // scale truncating floats",
                "code": '''def dequantize_weights(qweights: list[int], scale: float) -> list[float]:
    return [float(w // scale) for w in qweights]
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_cast_only",
                "description": "Casts to float without multiplying scale",
                "code": '''def dequantize_weights(qweights: list[int], scale: float) -> list[float]:
    return [float(w) for w in qweights]
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "quantization_math",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Dequantizes integer weights by multiplying float scale, preserving fractional precision."
    },

    # -------------------------------------------------------------------------
    # Task 043: vLLM Paged Attention Block Offset
    # -------------------------------------------------------------------------
    "task_043_vllm_paged_attention_block_offset": {
        "test_code": '''import pytest
from solution import compute_physical_slot

def test_oracle_happy_path_slot_lookup():
    block_table = [101, 102]
    phys_block, offset = compute_physical_slot(block_table, logical_pos=20, block_size=16)
    assert phys_block == 102
    assert offset == 4

def test_oracle_negative_negative_logical_pos():
    with pytest.raises(IndexError):
        compute_physical_slot([101], logical_pos=-1, block_size=16)

def test_oracle_negative_unallocated_block():
    with pytest.raises(IndexError):
        compute_physical_slot([101], logical_pos=32, block_size=16)

def test_oracle_negative_invalid_block_size():
    with pytest.raises(ValueError):
        compute_physical_slot([101], logical_pos=0, block_size=0)
''',
        "mutations": [
            {
                "id": "mutant_omit_negative_pos_check",
                "type": "out_of_bounds",
                "description": "Fails to guard against negative logical position",
                "code": '''def compute_physical_slot(block_table: list[int], logical_pos: int, block_size: int = 16) -> tuple[int, int]:
    block_idx = logical_pos // block_size
    offset = logical_pos % block_size
    physical_block = block_table[block_idx]
    return physical_block, offset
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_constant_offset",
                "description": "Returns fixed physical address",
                "code": '''def compute_physical_slot(block_table: list[int], logical_pos: int, block_size: int = 16) -> tuple[int, int]:
    return (block_table[0], 0)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "memory_virtualization",
            "SECURITY_SENSITIVITY": "high",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Translates logical KV cache positions to physical block addresses in PagedAttention, validating block size, bounds, and non-negativity."
    },

    # -------------------------------------------------------------------------
    # Task 044: vLLM KV Cache Concurrency Race
    # -------------------------------------------------------------------------
    "task_044_vllm_kv_cache_concurrency_race": {
        "test_code": '''import pytest
from solution import BlockAllocator

def test_oracle_happy_path_shared_block_refcount():
    alloc = BlockAllocator(num_blocks=2)
    b = alloc.allocate()
    alloc.share(b)
    alloc.free(b)
    assert b not in alloc.free_blocks
    alloc.free(b)
    assert b in alloc.free_blocks

def test_oracle_boundary_single_alloc_free():
    alloc = BlockAllocator(num_blocks=1)
    b = alloc.allocate()
    assert len(alloc.free_blocks) == 0
    alloc.free(b)
    assert len(alloc.free_blocks) == 1

def test_oracle_negative_out_of_blocks():
    alloc = BlockAllocator(num_blocks=1)
    alloc.allocate()
    with pytest.raises(RuntimeError, match="Out of blocks"):
        alloc.allocate()
''',
        "mutations": [
            {
                "id": "mutant_reclaim_without_refcount_check",
                "type": "double_free",
                "description": "Immediately reclaims block on first free without checking ref count",
                "code": '''class BlockAllocator:
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
        self.ref_counts[block_id] -= 1
        self.free_blocks.add(block_id)
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_never_free",
                "description": "Never adds block back to free_blocks",
                "code": '''class BlockAllocator:
    def __init__(self, num_blocks=10):
        self.free_blocks = set(range(num_blocks))
        self.ref_counts = {i: 0 for i in range(num_blocks)}
    def allocate(self) -> int:
        return self.free_blocks.pop()
    def share(self, block_id: int):
        pass
    def free(self, block_id: int):
        pass
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "ref_counting",
            "SECURITY_SENSITIVITY": "high",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "BlockAllocator manages reference counted physical KV cache blocks ensuring blocks are only recycled to free_blocks when ref count reaches zero."
    },

    # -------------------------------------------------------------------------
    # Task 045: vLLM Sampling Temperature Zero
    # -------------------------------------------------------------------------
    "task_045_vllm_sampling_temperature_zero": {
        "test_code": '''import pytest
from solution import sample_token

def test_oracle_happy_path_greedy_argmax():
    logits = [1.2, 5.8, 3.4]
    assert sample_token(logits, temperature=0.0) == 1

def test_oracle_happy_path_negative_temperature():
    logits = [10.0, 20.0]
    assert sample_token(logits, temperature=-0.5) == 1

def test_oracle_boundary_positive_temperature():
    logits = [0.0, 100.0]
    assert sample_token(logits, temperature=0.5) == 1
''',
        "mutations": [
            {
                "id": "mutant_unconditional_division",
                "type": "zero_division",
                "description": "Divides logits by temperature without checking temperature == 0.0",
                "code": '''def sample_token(logits: list[float], temperature: float = 0.0) -> int:
    scaled = [x / temperature for x in logits]
    return max(range(len(scaled)), key=lambda i: scaled[i])
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_return_zero_always",
                "description": "Returns index 0 always",
                "code": '''def sample_token(logits: list[float], temperature: float = 0.0) -> int:
    return 0
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "sampling_distribution",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Performs token sampling selecting greedy argmax deterministically when temperature <= 0.0 to prevent ZeroDivisionError."
    },

    # -------------------------------------------------------------------------
    # Task 046: vLLM Speculative Verification Rollback
    # -------------------------------------------------------------------------
    "task_046_vllm_speculative_verification_rollback": {
        "test_code": '''import pytest
from solution import verify_draft_tokens

def test_oracle_happy_path_break_on_first_mismatch():
    draft = [10, 20, 30, 40]
    target = [10, 99, 30, 40]
    accepted, rollback = verify_draft_tokens(draft, target)
    assert accepted == [10]
    assert rollback == 3

def test_oracle_boundary_all_tokens_match():
    draft = [1, 2, 3]
    target = [1, 2, 3]
    accepted, rollback = verify_draft_tokens(draft, target)
    assert accepted == [1, 2, 3]
    assert rollback == 0

def test_oracle_boundary_first_token_mismatches():
    draft = [9, 2]
    target = [1, 2]
    accepted, rollback = verify_draft_tokens(draft, target)
    assert accepted == []
    assert rollback == 2
''',
        "mutations": [
            {
                "id": "mutant_omit_break_on_mismatch",
                "type": "out_of_order_acceptance",
                "description": "Fails to break on mismatch, accepting subsequent tokens out of order",
                "code": '''def verify_draft_tokens(draft_tokens: list[int], target_tokens: list[int]) -> tuple[list[int], int]:
    accepted = []
    for d, t in zip(draft_tokens, target_tokens):
        if d == t:
            accepted.append(d)
    rollback = len(draft_tokens) - len(accepted)
    return accepted, rollback
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_accept_all_draft",
                "description": "Accepts all draft tokens without verification",
                "code": '''def verify_draft_tokens(draft_tokens: list[int], target_tokens: list[int]) -> tuple[list[int], int]:
    return (list(draft_tokens), 0)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "speculative_decoding",
            "SECURITY_SENSITIVITY": "medium",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Verifies speculative draft tokens against target tokens, stopping sequentially at the first mismatch and rolling back subsequent draft tokens."
    },

    # -------------------------------------------------------------------------
    # Task 047: MLflow Run Meta Logging
    # -------------------------------------------------------------------------
    "task_047_mlflow_run_meta_logging": {
        "test_code": '''import pytest
from solution import RunContext

def test_oracle_happy_path_parent_run_id_propagated():
    ctx = RunContext(run_id="child_1", parent_id="parent_0")
    ctx.init_tags()
    assert ctx.tags.get("mlflow.parentRunId") == "parent_0"
    assert ctx.tags.get("run_id") == "child_1"

def test_oracle_boundary_root_run_no_parent():
    ctx = RunContext(run_id="root_0", parent_id=None)
    ctx.init_tags()
    assert "mlflow.parentRunId" not in ctx.tags
    assert ctx.tags["run_id"] == "root_0"

def test_oracle_boundary_empty_string_parent():
    ctx = RunContext(run_id="child_empty", parent_id="")
    ctx.init_tags()
    assert "mlflow.parentRunId" not in ctx.tags
    assert ctx.tags["run_id"] == "child_empty"
''',
        "mutations": [
            {
                "id": "mutant_omit_parent_tag_assignment",
                "type": "missing_metadata",
                "description": "Omits setting mlflow.parentRunId tag",
                "code": '''class RunContext:
    def __init__(self, run_id: str, parent_id: str | None = None):
        self.run_id = run_id
        self.parent_id = parent_id
        self.tags = {}
    def init_tags(self):
        self.tags["run_id"] = self.run_id
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_hardcode_parent_id",
                "description": "Hardcodes parentRunId",
                "code": '''class RunContext:
    def __init__(self, run_id: str, parent_id: str | None = None):
        self.run_id = run_id
        self.parent_id = parent_id
        self.tags = {"mlflow.parentRunId": "hardcoded_parent", "run_id": run_id}
    def init_tags(self):
        pass
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "class_method",
            "ALGORITHM_COMPLEXITY": "O(1)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "metadata_logging",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateful_object",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Propagates hierarchical experiment lineage by automatically setting the mlflow.parentRunId tag on child runs."
    },

    # -------------------------------------------------------------------------
    # Task 048: MLflow Artifact Serialization Retry
    # -------------------------------------------------------------------------
    "task_048_mlflow_artifact_serialization_retry": {
        "test_code": '''import pytest
from solution import upload_artifact_with_retry

def test_oracle_happy_path_success_after_transient():
    call_count = 0
    def flaky_upload():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("503 Service Unavailable")
        return True
    assert upload_artifact_with_retry(flaky_upload, max_retries=4) is True
    assert call_count == 3

def test_oracle_negative_exhausted_retries():
    def broken_upload():
        raise RuntimeError("Persistent fail")
    with pytest.raises(RuntimeError, match="Upload failed after 3 attempts"):
        upload_artifact_with_retry(broken_upload, max_retries=3)

def test_oracle_boundary_instant_success():
    assert upload_artifact_with_retry(lambda: True, max_retries=1) is True
''',
        "mutations": [
            {
                "id": "mutant_no_retry_fail_immediately",
                "type": "missing_retry",
                "description": "Fails immediately on first exception without retrying",
                "code": '''def upload_artifact_with_retry(upload_fn, max_retries: int = 3) -> bool:
    try:
        return upload_fn()
    except Exception:
        raise RuntimeError("Upload failed after 1 attempts")
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_always_true",
                "description": "Always returns True without calling upload_fn",
                "code": '''def upload_artifact_with_retry(upload_fn, max_retries: int = 3) -> bool:
    return True
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "transient_fault_retry",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "medium"
        },
        "behavioral_spec": "Retries transient artifact upload exceptions up to max_retries times, returning result upon success or raising RuntimeError."
    },

    # -------------------------------------------------------------------------
    # Task 049: MLflow Metric Step Timestamp Sort
    # -------------------------------------------------------------------------
    "task_049_mlflow_metric_step_timestamp_sort": {
        "test_code": '''import pytest
from solution import sort_metric_history

def test_oracle_happy_path_sorted_by_step():
    m = [{"step": 10, "val": 0.8}, {"step": 2, "val": 0.2}, {"step": 5, "val": 0.5}]
    res = sort_metric_history(m)
    assert [x["step"] for x in res] == [2, 5, 10]

def test_oracle_boundary_already_sorted():
    m = [{"step": 1}, {"step": 2}]
    assert sort_metric_history(m) == m

def test_oracle_boundary_empty():
    assert sort_metric_history([]) == []
''',
        "mutations": [
            {
                "id": "mutant_unsorted_return",
                "type": "missing_sort",
                "description": "Returns metrics as-is without sorting",
                "code": '''def sort_metric_history(metrics: list[dict]) -> list[dict]:
    return metrics
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_reverse_sort",
                "description": "Sorts descending instead of ascending",
                "code": '''def sort_metric_history(metrics: list[dict]) -> list[dict]:
    return sorted(metrics, key=lambda m: m["step"], reverse=True)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N log N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "ordering_invariant",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Sorts out-of-order metric history lists in strictly non-decreasing order by the integer step field."
    },

    # -------------------------------------------------------------------------
    # Task 050: MLflow Model Signature Schema
    # -------------------------------------------------------------------------
    "task_050_mlflow_model_signature_schema": {
        "test_code": '''import pytest
from solution import validate_tensor_shape

def test_oracle_happy_path_dynamic_batch_size():
    expected = (-1, 128, 768)
    assert validate_tensor_shape((16, 128, 768), expected) is True
    assert validate_tensor_shape((1, 128, 768), expected) is True

def test_oracle_negative_mismatched_dimension():
    expected = (-1, 128, 768)
    assert validate_tensor_shape((16, 64, 768), expected) is False

def test_oracle_negative_rank_mismatch():
    expected = (-1, 128, 768)
    assert validate_tensor_shape((16, 128), expected) is False
''',
        "mutations": [
            {
                "id": "mutant_strict_dimension_comparison",
                "type": "wildcard_disallowed",
                "description": "Does not treat -1 as dynamic wildcard, requiring exact numeric match",
                "code": '''def validate_tensor_shape(actual_shape: tuple[int, ...], expected_shape: tuple[int, ...]) -> bool:
    if len(actual_shape) != len(expected_shape):
        return False
    for a, e in zip(actual_shape, expected_shape):
        if a != e:
            return False
    return True
'''
            }
        ],
        "plausible_bad_patches": [
            {
                "id": "bad_always_true_on_rank_match",
                "description": "Only compares rank, ignoring all dimension values",
                "code": '''def validate_tensor_shape(actual_shape: tuple[int, ...], expected_shape: tuple[int, ...]) -> bool:
    return len(actual_shape) == len(expected_shape)
'''
            }
        ],
        "difficulty": {
            "LOCALITY": "single_function",
            "ALGORITHM_COMPLEXITY": "O(N)",
            "CONTEXT_SIZE": "small",
            "DEPENDENCY_COMPLEXITY": "minimal",
            "TESTING_COMPLEXITY": "shape_wildcard_matching",
            "SECURITY_SENSITIVITY": "low",
            "STATEFULNESS": "stateless",
            "CONCURRENCY": "sequential",
            "DIFFICULTY_BUCKET": "easy"
        },
        "behavioral_spec": "Validates tensor dimensions against model signature schema treating -1 dimensions as dynamic wildcards while strictly enforcing matching rank and fixed dimensions."
    }
}
