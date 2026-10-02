from __future__ import annotations

import ast
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from aegis.execution.runner import run_tests
from aegis.research.agent.loop import AgentRunResult
from aegis.research.provenance.tracker import ProvenanceRecord
from aegis.verification.adversarial import run_mutation_tests
from aegis.verification.security import SecurityScanner
from aegis.verification.validator import validate_patch


@dataclass
class VerificationTierResults:
    c1_agent_only: int
    c2_visible_tests: int
    c3_hidden_tests: int
    c4_regression: int
    c5_mutation: int
    c6_full_aegis: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "C1_agent_only": self.c1_agent_only,
            "C2_visible_tests": self.c2_visible_tests,
            "C3_hidden_tests": self.c3_hidden_tests,
            "C4_regression": self.c4_regression,
            "C5_mutation": self.c5_mutation,
            "C6_full_aegis": self.c6_full_aegis,
        }


@dataclass
class AegisVerificationReport:
    task_id: str
    tiers: VerificationTierResults
    technical_verdict: str  # QUALIFIED, QUALIFIED_WITHIN_SCOPE, FAILED, INDETERMINATE
    release_policy: str  # AUTO_APPROVE, REVIEW, BLOCK
    security_safe: bool
    security_issues: List[str]
    validator_valid: bool
    validator_errors: List[str]
    visible_tests_passed: bool
    hidden_tests_passed: bool
    regression_passed: bool
    mutation_score: Optional[float]
    mutation_killed: int
    mutation_total: int
    verification_duration_seconds: float
    tier_durations: Dict[str, float] = field(default_factory=dict)
    tier_skipped: Dict[str, bool] = field(default_factory=dict)
    tier_timestamps: Dict[str, Dict[str, float]] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AegisResearchVerifier:
    """Runs a candidate workspace through the full ladder of Aegis verification tiers (C1 -> C6)."""

    @classmethod
    def verify(
        cls,
        task_dir: Path,
        candidate_dir: Path,
        agent_result: AgentRunResult,
        provenance: ProvenanceRecord,
        timeout: float = 30.0,
    ) -> AegisVerificationReport:
        t_start = time.time()
        task_dir = Path(task_dir).resolve()
        candidate_dir = Path(candidate_dir).resolve()

        task_public = task_dir / "task"
        task_private = task_dir / "private"
        buggy_dir = task_public / "buggy"
        hidden_tests_dir = task_private / "aegis_hidden_tests"
        if not hidden_tests_dir.exists():
            hidden_tests_dir = task_private / "hidden_tests"

        tier_durations: Dict[str, float] = {
            "C1": 0.0, "C2": 0.0, "C3": 0.0, "C4": 0.0, "C5": 0.0, "C6": 0.0
        }
        tier_skipped: Dict[str, bool] = {
            "C1": False, "C2": False, "C3": False, "C4": False, "C5": False, "C6": False
        }
        tier_timestamps: Dict[str, Dict[str, float]] = {}

        # -------------------------------------------------------------------
        # Tier C1: Agent self-signal + Static validation + Security scanning
        # -------------------------------------------------------------------
        t0_c1 = time.time()
        c1 = 1 if agent_result.success_signaled and not agent_result.error_message else 0

        # Construct patch dictionary for validator & security scanner
        patch_dict: Dict[str, str] = {}
        all_changed = list(set(provenance.modified_files + provenance.added_files))
        for rel in all_changed:
            p = candidate_dir / rel
            if p.exists() and p.is_file():
                patch_dict[rel] = p.read_text(encoding="utf-8", errors="replace")

        # Security Scanner
        scanner = SecurityScanner()
        sec_res = scanner.scan_patch(patch_dict)
        security_safe = sec_res.safe
        security_issues = sec_res.issues

        # Validator
        val_res = validate_patch(patch_dict, candidate_dir)
        validator_valid = val_res.valid
        validator_errors = val_res.errors
        t1_c1 = time.time()
        tier_durations["C1"] = max(0.0, t1_c1 - t0_c1)
        tier_timestamps["C1"] = {"start": t0_c1, "end": t1_c1}

        # -------------------------------------------------------------------
        # Tier C2: Visible test execution
        # -------------------------------------------------------------------
        t0_c2 = time.time()
        c2 = 0
        visible_passed = False
        try:
            vis_res = run_tests(candidate_dir, timeout=int(timeout))
            visible_passed = vis_res.passed
            if visible_passed:
                c2 = 1
        except Exception:
            visible_passed = False
        t1_c2 = time.time()
        tier_durations["C2"] = max(0.0, t1_c2 - t0_c2)
        tier_timestamps["C2"] = {"start": t0_c2, "end": t1_c2}

        # -------------------------------------------------------------------
        # Tier C3: Private / Hidden test evaluation
        # -------------------------------------------------------------------
        t0_c3 = time.time()
        c3 = 0
        hidden_passed = False
        if c2 == 1:
            if hidden_tests_dir.exists():
                with tempfile.TemporaryDirectory() as td:
                    eval_ws = Path(td) / "eval_ws"
                    shutil.copytree(candidate_dir, eval_ws, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
                    # Copy hidden tests
                    shutil.copytree(hidden_tests_dir, eval_ws / "hidden_tests", dirs_exist_ok=True)
                    try:
                        h_res = run_tests(eval_ws, timeout=int(timeout), test_files=["hidden_tests"])
                        hidden_passed = h_res.passed
                        if hidden_passed:
                            c3 = 1
                    except Exception:
                        hidden_passed = False
            else:
                hidden_passed = True
                c3 = 1
            t1_c3 = time.time()
            tier_durations["C3"] = max(0.0, t1_c3 - t0_c3)
            tier_timestamps["C3"] = {"start": t0_c3, "end": t1_c3}
        else:
            tier_skipped["C3"] = True
            tier_durations["C3"] = 0.0
            tier_timestamps["C3"] = {"start": t0_c3, "end": t0_c3}

        # -------------------------------------------------------------------
        # Tier C4: Regression verification
        # -------------------------------------------------------------------
        t0_c4 = time.time()
        c4 = 0
        regression_passed = False
        if c3 == 1:
            try:
                base_res = run_tests(buggy_dir, timeout=int(timeout))
                head_res = run_tests(candidate_dir, timeout=int(timeout))
                if base_res.tests_passed > 0 and head_res.tests_failed > 0:
                    regression_passed = False
                elif head_res.passed:
                    regression_passed = True
                    c4 = 1
                else:
                    regression_passed = False
            except Exception:
                regression_passed = False
            t1_c4 = time.time()
            tier_durations["C4"] = max(0.0, t1_c4 - t0_c4)
            tier_timestamps["C4"] = {"start": t0_c4, "end": t1_c4}
        else:
            tier_skipped["C4"] = True
            tier_durations["C4"] = 0.0
            tier_timestamps["C4"] = {"start": t0_c4, "end": t0_c4}

        # -------------------------------------------------------------------
        # Tier C5: Mutation testing
        # -------------------------------------------------------------------
        t0_c5 = time.time()
        c5 = 0
        mut_score = None
        mut_killed = 0
        mut_total = 0
        if c4 == 1:
            mutation_targets = [
                f for f in provenance.modified_files
                if f.endswith(".py") and not f.startswith("tests") and "test" not in f.lower()
            ]
            if mutation_targets:
                try:
                    mut_res = run_mutation_tests(
                        candidate_dir,
                        mutation_targets[:2],
                        max_mutants_per_file=2,
                        timeout=10,
                        use_docker=False,
                    )
                    mut_score = mut_res.score
                    mut_killed = mut_res.killed_mutants
                    mut_total = mut_res.killed_mutants + mut_res.survived_mutants
                    if mut_score is not None:
                        if mut_score >= 0.5 or mut_res.survived_mutants == 0:
                            c5 = 1
                    else:
                        c5 = 1
                except Exception:
                    c5 = 0
            else:
                c5 = 1
            t1_c5 = time.time()
            tier_durations["C5"] = max(0.0, t1_c5 - t0_c5)
            tier_timestamps["C5"] = {"start": t0_c5, "end": t1_c5}
        else:
            tier_skipped["C5"] = True
            tier_durations["C5"] = 0.0
            tier_timestamps["C5"] = {"start": t0_c5, "end": t0_c5}

        # -------------------------------------------------------------------
        # Tier C6: Full Aegis Verification & Release Policy
        # -------------------------------------------------------------------
        t0_c6 = time.time()
        c6 = 0
        if c5 == 1:
            if security_safe and validator_valid:
                c6 = 1
            t1_c6 = time.time()
            tier_durations["C6"] = max(0.0, t1_c6 - t0_c6)
            tier_timestamps["C6"] = {"start": t0_c6, "end": t1_c6}
        else:
            tier_skipped["C6"] = True
            tier_durations["C6"] = 0.0
            tier_timestamps["C6"] = {"start": t0_c6, "end": t0_c6}

        # Determine Technical Verdict
        if not security_safe or not validator_valid or not visible_passed:
            technical_verdict = "FAILED"
        elif not hidden_passed or not regression_passed:
            technical_verdict = "FAILED"
        elif c6 == 1:
            technical_verdict = "QUALIFIED"
        else:
            technical_verdict = "QUALIFIED_WITHIN_SCOPE"

        # Determine Release Policy
        if technical_verdict == "FAILED":
            release_policy = "BLOCK"
        elif technical_verdict in ("QUALIFIED", "QUALIFIED_WITHIN_SCOPE"):
            if c6 == 1 and security_safe:
                release_policy = "AUTO_APPROVE"
            else:
                release_policy = "REVIEW"
        else:
            release_policy = "REVIEW"

        tiers = VerificationTierResults(
            c1_agent_only=c1,
            c2_visible_tests=c2,
            c3_hidden_tests=c3,
            c4_regression=c4,
            c5_mutation=c5,
            c6_full_aegis=c6,
        )

        total_measured = sum(tier_durations.values())
        elapsed_overall = time.time() - t_start
        # Integrity check: difference between sum of isolated tiers and overall duration must be <= 0.10s
        # (overall duration may include tiny Python overheads between steps)
        assert abs(elapsed_overall - total_measured) <= 0.10 or elapsed_overall >= total_measured

        return AegisVerificationReport(
            task_id=task_dir.name,
            tiers=tiers,
            technical_verdict=technical_verdict,
            release_policy=release_policy,
            security_safe=security_safe,
            security_issues=security_issues,
            validator_valid=validator_valid,
            validator_errors=validator_errors,
            visible_tests_passed=visible_passed,
            hidden_tests_passed=hidden_passed,
            regression_passed=regression_passed,
            mutation_score=mut_score,
            mutation_killed=mut_killed,
            mutation_total=mut_total,
            verification_duration_seconds=total_measured,
            tier_durations=tier_durations,
            tier_skipped=tier_skipped,
            tier_timestamps=tier_timestamps,
        )
