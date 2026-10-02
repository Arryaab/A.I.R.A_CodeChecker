from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from aegis.research.agent.loop import AgentRunResult
from aegis.research.provenance.tracker import ProvenanceRecord

PRE_VERIFICATION_FEATURE_NAMES = [
    "lines_added",
    "lines_deleted",
    "net_churn",
    "files_changed",
    "functions_changed",
    "public_api_delta",
    "dependency_fan_out",
    "call_graph_dist",
    "defect_history",
    "cc_delta",
    "nesting_depth_delta",
    "ast_nodes_delta",
    "agent_retry_count",
    "tool_call_count",
    "prompt_tokens",
    "completion_tokens",
    "linter_delta",
    "changed_test_files",
    "test_modification_flag",
]


def _count_ast_nodes(code: str) -> int:
    try:
        tree = ast.parse(code)
        return len(list(ast.walk(tree)))
    except Exception:
        return 0


def _cyclomatic_complexity(code: str) -> int:
    """Computes McCabe cyclomatic complexity: 1 + decision points."""
    try:
        tree = ast.parse(code)
    except Exception:
        return 1

    decision_nodes = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.ExceptHandler,
        ast.With,
        ast.AsyncWith,
        ast.Assert,
    )
    score = 1
    for node in ast.walk(tree):
        if isinstance(node, decision_nodes):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
    return score


def _max_nesting_depth(code: str) -> int:
    """Calculates maximum block nesting depth via AST hierarchy."""
    try:
        tree = ast.parse(code)
    except Exception:
        return 0

    block_types = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncWith,
    )

    def _walk_depth(node: ast.AST, current_depth: int) -> int:
        max_d = current_depth
        for child in ast.iter_child_nodes(node):
            next_d = current_depth + 1 if isinstance(child, block_types) else current_depth
            sub = _walk_depth(child, next_d)
            if sub > max_d:
                max_d = sub
        return max_d

    return _walk_depth(tree, 0)


def _extract_imports(code: str) -> set[str]:
    """Extract set of imported module names."""
    imports = set()
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.add(n.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    except Exception:
        pass
    return imports


def _check_public_api_delta(base_code: str, head_code: str) -> int:
    """Check if any public function/class was added, removed, or changed signature."""
    try:
        t1 = ast.parse(base_code)
        t2 = ast.parse(head_code)
    except Exception:
        return 0

    def get_public_defs(tree: ast.AST) -> Dict[str, str]:
        defs = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    args = [a.arg for a in node.args.args]
                    defs[node.name] = f"def {node.name}({','.join(args)})"
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    defs[node.name] = f"class {node.name}"
        return defs

    pub1 = get_public_defs(t1)
    pub2 = get_public_defs(t2)

    return 1 if pub1 != pub2 else 0


@dataclass
class PreVerificationFeatures:
    lines_added: int
    lines_deleted: int
    net_churn: int
    files_changed: int
    functions_changed: int
    public_api_delta: int
    dependency_fan_out: int
    call_graph_dist: int
    defect_history: float
    cc_delta: int
    nesting_depth_delta: int
    ast_nodes_delta: int
    agent_retry_count: int
    tool_call_count: int
    prompt_tokens: int
    completion_tokens: int
    linter_delta: int
    changed_test_files: int
    test_modification_flag: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_vector(self) -> List[float]:
        """Strictly 19-element pre-verification feature vector with zero target leakage."""
        return [
            float(self.lines_added),
            float(self.lines_deleted),
            float(self.net_churn),
            float(self.files_changed),
            float(self.functions_changed),
            float(self.public_api_delta),
            float(self.dependency_fan_out),
            float(self.call_graph_dist),
            float(self.defect_history),
            float(self.cc_delta),
            float(self.nesting_depth_delta),
            float(self.ast_nodes_delta),
            float(self.agent_retry_count),
            float(self.tool_call_count),
            float(self.prompt_tokens),
            float(self.completion_tokens),
            float(self.linter_delta),
            float(self.changed_test_files),
            float(self.test_modification_flag),
        ]


class PreVerificationFeatureExtractor:
    """Extracts features strictly prior to execution and verification.
    Guarantees no target or test runtime signal leakage.
    """

    @staticmethod
    def extract(
        provenance: ProvenanceRecord,
        agent_result: AgentRunResult,
        base_dir: Path,
        head_dir: Path,
        task_category: str = "core",
    ) -> PreVerificationFeatures:
        # 1. Churn and file counts
        lines_added = provenance.lines_added
        lines_deleted = provenance.lines_deleted
        net_churn = provenance.net_churn
        all_changed_files = list(set(provenance.modified_files + provenance.added_files + provenance.deleted_files))
        files_changed = len(all_changed_files)

        # 2. Test modifications
        test_files_touched = [
            f for f in all_changed_files
            if "test" in f.lower() or Path(f).name.startswith("test_") or Path(f).name.endswith("_test.py")
        ]
        changed_test_files = len(test_files_touched)
        test_modification_flag = 1 if changed_test_files > 0 else 0

        # 3. AST and complexity deltas
        functions_changed = len(provenance.ast_delta.functions_modified) + len(provenance.ast_delta.functions_added)

        total_cc_delta = 0
        total_nesting_delta = 0
        total_nodes_delta = 0
        public_api_delta = 0
        all_new_imports = set()
        max_call_dist = 1

        for rel in provenance.modified_files:
            b_path = base_dir / rel
            h_path = head_dir / rel
            if b_path.exists() and h_path.exists() and rel.endswith(".py"):
                b_code = b_path.read_text(encoding="utf-8", errors="replace")
                h_code = h_path.read_text(encoding="utf-8", errors="replace")

                # Cyclomatic complexity delta
                cc_b = _cyclomatic_complexity(b_code)
                cc_h = _cyclomatic_complexity(h_code)
                total_cc_delta += (cc_h - cc_b)

                # Nesting depth delta
                nd_b = _max_nesting_depth(b_code)
                nd_h = _max_nesting_depth(h_code)
                total_nesting_delta += (nd_h - nd_b)

                # AST nodes delta
                n_b = _count_ast_nodes(b_code)
                n_h = _count_ast_nodes(h_code)
                total_nodes_delta += (n_h - n_b)

                # Public API
                if _check_public_api_delta(b_code, h_code) == 1:
                    public_api_delta = 1

                # Imports
                imp_b = _extract_imports(b_code)
                imp_h = _extract_imports(h_code)
                all_new_imports.update(imp_h - imp_b)

                # Call graph dist / directory depth
                depth = len(Path(rel).parts)
                if depth > max_call_dist:
                    max_call_dist = depth

        # 4. Domain defect history prior (calibrated by task category)
        category_defect_priors = {
            "core": 0.12,
            "scientific": 0.18,
            "aiml": 0.24,
            "framework_lifecycle": 0.20,
            "concurrency": 0.28,
            "security": 0.15,
        }
        defect_history = category_defect_priors.get(task_category.lower(), 0.15)

        # 5. Agent execution metrics
        tool_calls_count = sum(len(step.tool_calls) for step in agent_result.steps)
        retry_count = sum(1 for step in agent_result.steps if any(tc["name"] == "run_tests" for tc in step.tool_calls))
        prompt_tokens = agent_result.total_prompt_tokens
        completion_tokens = agent_result.total_completion_tokens

        # 6. Syntax / linter delta
        linter_delta = 0
        for rel in provenance.modified_files:
            h_path = head_dir / rel
            if h_path.exists() and rel.endswith(".py"):
                try:
                    ast.parse(h_path.read_text(encoding="utf-8", errors="replace"))
                except SyntaxError:
                    linter_delta += 1

        return PreVerificationFeatures(
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            net_churn=net_churn,
            files_changed=files_changed,
            functions_changed=functions_changed,
            public_api_delta=public_api_delta,
            dependency_fan_out=len(all_new_imports),
            call_graph_dist=max_call_dist,
            defect_history=defect_history,
            cc_delta=total_cc_delta,
            nesting_depth_delta=total_nesting_delta,
            ast_nodes_delta=total_nodes_delta,
            agent_retry_count=retry_count,
            tool_call_count=tool_calls_count,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            linter_delta=linter_delta,
            changed_test_files=changed_test_files,
            test_modification_flag=test_modification_flag,
        )
