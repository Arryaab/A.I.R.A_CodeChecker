"""
Curated demo scenarios for Aegis Public Release 1.0.

Provides deterministic, reproducible verification runs illustrating the 5 critical
failure/success modes in AI-generated code changes without requiring live Docker
daemons or external cloud credentials.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List

DEMO_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "demo_01_clean_pass": {
        "id": "demo_01_clean_pass",
        "title": "Clean Verified Patch (Token Bucket Rate Limiter)",
        "category": "High Assurance / Clean Pass",
        "badge": "PASS",
        "description": "AI agent implemented a thread-safe token bucket rate limiter with monotonic clock precision, clean boundary checks, and full regression test coverage.",
        "file_path": "services/rate_limiter.py",
        "diff": """--- a/services/rate_limiter.py
+++ b/services/rate_limiter.py
@@ -14,6 +14,24 @@
 class TokenBucket:
     def __init__(self, capacity: int, refill_rate: float):
+        if capacity <= 0:
+            raise ValueError("Capacity must be positive")
+        if refill_rate <= 0:
+            raise ValueError("Refill rate must be positive")
         self.capacity = float(capacity)
         self.tokens = float(capacity)
         self.refill_rate = float(refill_rate)
-        self.last_refill = time.time()
+        self.last_refill = time.monotonic()
+        self._lock = threading.Lock()
+
+    def consume(self, tokens: int = 1) -> bool:
+        if tokens <= 0:
+            raise ValueError("Tokens to consume must be positive")
+        with self._lock:
+            now = time.monotonic()
+            elapsed = now - self.last_refill
+            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
+            self.last_refill = now
+            if self.tokens >= tokens:
+                self.tokens -= tokens
+                return True
+            return False
""",
        "technical_verdict": "QUALIFIED",
        "release_policy": "AUTO_APPROVE",
        "risk_level": "LOW",
        "execution_tier": "STANDARD",
        "duration_ms": 1420,
        "criteria": {
            "C1_syntax": {
                "name": "C1: Syntax & AST Integrity",
                "status": "PASS",
                "score": 1.0,
                "detail": "AST parsed cleanly; zero syntax errors, valid type annotations."
            },
            "C2_visible_tests": {
                "name": "C2: Visible Acceptance Tests",
                "status": "PASS",
                "score": 1.0,
                "detail": "8/8 acceptance tests passed (100% pass rate)."
            },
            "C3_hidden_invariants": {
                "name": "C3: Hidden Invariants & Edge Cases",
                "status": "PASS",
                "score": 1.0,
                "detail": "12/12 boundary and negative condition invariant tests passed."
            },
            "C4_regression": {
                "name": "C4: Regression Suite",
                "status": "PASS",
                "score": 1.0,
                "detail": "34/34 existing regression tests passed; zero signature or runtime regressions."
            },
            "C5_mutation": {
                "name": "C5: Mutation Resistance",
                "status": "PASS",
                "score": 0.92,
                "detail": "Mutation score: 91.7% (11/12 mutants killed). High semantic density."
            },
            "C6_security": {
                "name": "C6: Security AST & Taint Scan",
                "status": "PASS",
                "score": 1.0,
                "detail": "Zero CWE triggers, thread-safe primitives verified, no dangerous calls."
            }
        },
        "mlverify": {
            "mode": "SHADOW_MODE_ONLY",
            "defect_risk": 0.042,
            "risk_band": "LOW",
            "recommended_tier": "FAST",
            "confidence": 0.958,
            "shadow_agreement": True,
            "explanation": "Predicted low risk based on bounded AST modifications, high test-to-code ratio, and pure idempotent logic. Matches actual outcome."
        },
        "events": [
            {"stage": "INITIALIZE", "message": "Verification worker spawned in isolated sandbox environment", "ms_offset": 50},
            {"stage": "INDEXING", "message": "Analyzing repository diff: services/rate_limiter.py (+24, -2)", "ms_offset": 120},
            {"stage": "C1_SYNTAX", "message": "AST validation passed with 0 warnings or syntax errors", "ms_offset": 240},
            {"stage": "C2_TESTS", "message": "Running 8 acceptance unit tests... 8 PASSED (100%)", "ms_offset": 510},
            {"stage": "C3_INVARIANTS", "message": "Exercising 12 hidden invariant property tests... 12 PASSED", "ms_offset": 820},
            {"stage": "C4_REGRESSION", "message": "Running full regression suite (34 tests)... 34 PASSED", "ms_offset": 1050},
            {"stage": "C5_MUTATION", "message": "Generating 12 AST mutants... 11 killed, 1 survived (Score: 0.92)", "ms_offset": 1280},
            {"stage": "C6_SECURITY", "message": "AST security visitor: 0 taint sinks, no unvetted subprocess/eval", "ms_offset": 1360},
            {"stage": "MLVERIFY_SHADOW", "message": "MLVerify shadow prediction: Defect Risk 4.2% [LOW], recommends FAST", "ms_offset": 1390},
            {"stage": "POLICY_GATE", "message": "Decision: QUALIFIED | Release Policy: AUTO_APPROVE", "ms_offset": 1420}
        ]
    },

    "demo_02_hidden_overfit": {
        "id": "demo_02_hidden_overfit",
        "title": "Hidden Invariant Failure (Zero-Division Edge Case)",
        "category": "AI Overfitting / Hidden Defects",
        "badge": "FAIL",
        "description": "AI agent implemented a batch inventory rebalancing algorithm that passes all visible prompt tests, but silently crashes with ZeroDivisionError when total batch demand is zero.",
        "file_path": "orders/inventory_allocator.py",
        "diff": """--- a/orders/inventory_allocator.py
+++ b/orders/inventory_allocator.py
@@ -32,7 +32,13 @@
 def rebalance_stock(warehouse_inventory: dict[str, int], order_demands: dict[str, int]) -> dict[str, float]:
     \"\"\"Calculates proportional allocation ratio for multi-warehouse fulfillments.\"\"\"
-    pass
+    total_demand = sum(order_demands.values())
+    allocated = {}
+    for sku, available in warehouse_inventory.items():
+        demand = order_demands.get(sku, 0)
+        # BUG: Fails when total_demand is 0 (e.g. empty cart or cancelled batch)
+        ratio = demand / total_demand
+        allocated[sku] = round(available * ratio, 2)
+    return allocated
""",
        "technical_verdict": "REJECTED",
        "release_policy": "BLOCK",
        "risk_level": "HIGH",
        "execution_tier": "STANDARD",
        "duration_ms": 1180,
        "criteria": {
            "C1_syntax": {
                "name": "C1: Syntax & AST Integrity",
                "status": "PASS",
                "score": 1.0,
                "detail": "Valid syntax."
            },
            "C2_visible_tests": {
                "name": "C2: Visible Acceptance Tests",
                "status": "PASS",
                "score": 1.0,
                "detail": "4/4 visible acceptance tests passed. (AI successfully overfitted visible cases)."
            },
            "C3_hidden_invariants": {
                "name": "C3: Hidden Invariants & Edge Cases",
                "status": "FAIL",
                "score": 0.0,
                "detail": "CRITICAL: ZeroDivisionError encountered on zero-demand edge case (order_demands={'item_a': 0})."
            },
            "C4_regression": {
                "name": "C4: Regression Suite",
                "status": "PASS",
                "score": 1.0,
                "detail": "18/18 existing regression tests passed."
            },
            "C5_mutation": {
                "name": "C5: Mutation Resistance",
                "status": "SKIPPED",
                "score": 0.0,
                "detail": "Skipped due to upstream invariant gate failure."
            },
            "C6_security": {
                "name": "C6: Security AST & Taint Scan",
                "status": "PASS",
                "score": 1.0,
                "detail": "No direct security AST violations."
            }
        },
        "mlverify": {
            "mode": "SHADOW_MODE_ONLY",
            "defect_risk": 0.745,
            "risk_band": "HIGH",
            "recommended_tier": "DEEP",
            "confidence": 0.882,
            "shadow_agreement": True,
            "explanation": "Flagged high defect likelihood due to unshielded division operator on aggregate variable without precondition guard."
        },
        "events": [
            {"stage": "INITIALIZE", "message": "Verification worker spawned in isolated sandbox environment", "ms_offset": 40},
            {"stage": "INDEXING", "message": "Analyzing repository diff: orders/inventory_allocator.py (+8, -1)", "ms_offset": 110},
            {"stage": "C1_SYNTAX", "message": "AST validation passed: valid Python syntax", "ms_offset": 220},
            {"stage": "C2_TESTS", "message": "Running 4 visible unit tests... 4 PASSED (Overfitted)", "ms_offset": 480},
            {"stage": "C3_INVARIANTS", "message": "TEST FAILURE in test_zero_demand_invariant: ZeroDivisionError: division by zero", "ms_offset": 750},
            {"stage": "C4_REGRESSION", "message": "Running standard regression suite... 18 PASSED", "ms_offset": 920},
            {"stage": "C5_MUTATION", "message": "Skipping mutation analysis due to failed invariant gate", "ms_offset": 980},
            {"stage": "C6_SECURITY", "message": "Security AST scanner: Clean", "ms_offset": 1050},
            {"stage": "MLVERIFY_SHADOW", "message": "MLVerify shadow prediction: Defect Risk 74.5% [HIGH], recommends DEEP", "ms_offset": 1120},
            {"stage": "POLICY_GATE", "message": "Decision: REJECTED | Release Policy: BLOCK (Invariant C3 Violated)", "ms_offset": 1180}
        ]
    },

    "demo_03_path_traversal": {
        "id": "demo_03_path_traversal",
        "title": "Security Boundary Violation (Path Traversal in Export Worker)",
        "category": "Security / AST Taint Analysis",
        "badge": "FAIL",
        "description": "AI agent implemented a file export endpoint that accepts an arbitrary filename parameter and performs unvalidated path joining, exposing arbitrary filesystem access.",
        "file_path": "reports/export_worker.py",
        "diff": """--- a/reports/export_worker.py
+++ b/reports/export_worker.py
@@ -19,5 +19,13 @@
 def save_report_output(report_id: str, filename: str, content: bytes) -> str:
     base_dir = "/var/reports/generated"
-    target = os.path.join(base_dir, f"{report_id}.pdf")
+    # SECURITY VULNERABILITY: filename parameter is directly concatenated
+    # Allows attacks like filename='../../etc/cron.d/malicious'
+    target = os.path.join(base_dir, filename)
     with open(target, "wb") as f:
         f.write(content)
     return target
""",
        "technical_verdict": "REJECTED",
        "release_policy": "BLOCK",
        "risk_level": "CRITICAL",
        "execution_tier": "DEEP",
        "duration_ms": 940,
        "criteria": {
            "C1_syntax": {
                "name": "C1: Syntax & AST Integrity",
                "status": "PASS",
                "score": 1.0,
                "detail": "Syntax check clean."
            },
            "C2_visible_tests": {
                "name": "C2: Visible Acceptance Tests",
                "status": "PASS",
                "score": 1.0,
                "detail": "Basic save test passed for valid benign filename."
            },
            "C3_hidden_invariants": {
                "name": "C3: Hidden Invariants & Edge Cases",
                "status": "PASS",
                "score": 1.0,
                "detail": "Basic functional invariants passed."
            },
            "C4_regression": {
                "name": "C4: Regression Suite",
                "status": "PASS",
                "score": 1.0,
                "detail": "Legacy report generator tests passed."
            },
            "C5_mutation": {
                "name": "C5: Mutation Resistance",
                "status": "SKIPPED",
                "score": 0.0,
                "detail": "Bypassed due to critical security veto."
            },
            "C6_security": {
                "name": "C6: Security AST & Taint Scan",
                "status": "FAIL",
                "score": 0.0,
                "detail": "CRITICAL: CWE-22 (Path Traversal) flagged by AST taint analyzer. Parameter 'filename' flows into file system write sink without os.path.abspath/secure_filename sanitization."
            }
        },
        "mlverify": {
            "mode": "SHADOW_MODE_ONLY",
            "defect_risk": 0.891,
            "risk_band": "HIGH",
            "recommended_tier": "DEEP",
            "confidence": 0.914,
            "shadow_agreement": True,
            "explanation": "Flagged high defect risk based on untrusted argument routing to filesystem I/O sinks without sanitizing wrappers."
        },
        "events": [
            {"stage": "INITIALIZE", "message": "Verification worker spawned in isolated sandbox environment", "ms_offset": 30},
            {"stage": "INDEXING", "message": "Analyzing repository diff: reports/export_worker.py (+5, -1)", "ms_offset": 90},
            {"stage": "C1_SYNTAX", "message": "AST validation passed: valid syntax", "ms_offset": 180},
            {"stage": "C2_TESTS", "message": "Acceptance tests: 2/2 passed with benign test data", "ms_offset": 390},
            {"stage": "C3_INVARIANTS", "message": "Functional invariants: 4/4 passed", "ms_offset": 580},
            {"stage": "C4_REGRESSION", "message": "Regression suite: 12/12 passed", "ms_offset": 740},
            {"stage": "C6_SECURITY", "message": "SECURITY VETO: CWE-22 Path Traversal in os.path.join(base_dir, filename)", "ms_offset": 860},
            {"stage": "MLVERIFY_SHADOW", "message": "MLVerify shadow prediction: Defect Risk 89.1% [HIGH], recommends DEEP", "ms_offset": 910},
            {"stage": "POLICY_GATE", "message": "Decision: REJECTED | Release Policy: BLOCK (Security AST Veto)", "ms_offset": 940}
        ]
    },

    "demo_04_regression_break": {
        "id": "demo_04_regression_break",
        "title": "Backward Compatibility Regression (API Schema Break)",
        "category": "Regression / Downstream Impact",
        "badge": "FAIL",
        "description": "AI agent refactored a payment webhook handler to support v2 payloads, but accidentally renamed the legacy dictionary key 'transaction_id' to 'tx_id', breaking downstream consumers.",
        "file_path": "payments/webhook_dispatcher.py",
        "diff": """--- a/payments/webhook_dispatcher.py
+++ b/payments/webhook_dispatcher.py
@@ -45,8 +45,8 @@
 def format_webhook_event(raw_event: dict) -> dict:
     return {
         "event_type": raw_event.get("type", "unknown"),
-        "transaction_id": raw_event.get("txn_id"),
-        "status": raw_event.get("status")
+        # BREAKING REGRESSION: Renamed key breaks downstream microservices expecting 'transaction_id'
+        "tx_id": raw_event.get("txn_id"),
+        "status": raw_event.get("status")
     }
""",
        "technical_verdict": "REJECTED",
        "release_policy": "BLOCK",
        "risk_level": "HIGH",
        "execution_tier": "STANDARD",
        "duration_ms": 1310,
        "criteria": {
            "C1_syntax": {
                "name": "C1: Syntax & AST Integrity",
                "status": "PASS",
                "score": 1.0,
                "detail": "Syntax clean."
            },
            "C2_visible_tests": {
                "name": "C2: Visible Acceptance Tests",
                "status": "PASS",
                "score": 1.0,
                "detail": "New v2 webhook parser unit tests passed (3/3)."
            },
            "C3_hidden_invariants": {
                "name": "C3: Hidden Invariants & Edge Cases",
                "status": "PASS",
                "score": 1.0,
                "detail": "Event schema invariants satisfied."
            },
            "C4_regression": {
                "name": "C4: Regression Suite",
                "status": "FAIL",
                "score": 0.0,
                "detail": "CRITICAL REGRESSION: 3 downstream tests failed! KeyError: 'transaction_id' in tests/test_billing_integration.py."
            },
            "C5_mutation": {
                "name": "C5: Mutation Resistance",
                "status": "SKIPPED",
                "score": 0.0,
                "detail": "Skipped due to regression suite failure."
            },
            "C6_security": {
                "name": "C6: Security AST & Taint Scan",
                "status": "PASS",
                "score": 1.0,
                "detail": "No security violations."
            }
        },
        "mlverify": {
            "mode": "SHADOW_MODE_ONLY",
            "defect_risk": 0.723,
            "risk_band": "HIGH",
            "recommended_tier": "STANDARD",
            "confidence": 0.865,
            "shadow_agreement": True,
            "explanation": "Predicted elevated regression risk due to dictionary output schema alteration without deprecation mapping."
        },
        "events": [
            {"stage": "INITIALIZE", "message": "Verification worker spawned in isolated sandbox environment", "ms_offset": 45},
            {"stage": "INDEXING", "message": "Analyzing repository diff: payments/webhook_dispatcher.py (+3, -2)", "ms_offset": 115},
            {"stage": "C1_SYNTAX", "message": "AST validation passed: valid syntax", "ms_offset": 230},
            {"stage": "C2_TESTS", "message": "Running v2 webhook acceptance tests... 3 PASSED", "ms_offset": 520},
            {"stage": "C3_INVARIANTS", "message": "Checking invariant schema constraints... PASSED", "ms_offset": 760},
            {"stage": "C4_REGRESSION", "message": "REGRESSION FAILURE: 3 tests failed in downstream suite! KeyError: 'transaction_id'", "ms_offset": 1110},
            {"stage": "C6_SECURITY", "message": "Security AST scan: 0 findings", "ms_offset": 1210},
            {"stage": "MLVERIFY_SHADOW", "message": "MLVerify shadow prediction: Defect Risk 72.3% [HIGH], recommends STANDARD", "ms_offset": 1260},
            {"stage": "POLICY_GATE", "message": "Decision: REJECTED | Release Policy: BLOCK (Regression in C4 Suite)", "ms_offset": 1310}
        ]
    },

    "demo_05_mutation_survivor": {
        "id": "demo_05_mutation_survivor",
        "title": "Mutation-Resistant Semantic Defect (Vacuous Boundary Condition)",
        "category": "Semantic Verification / Mutation Testing",
        "badge": "REVIEW",
        "description": "AI agent wrote a discount calculation with a tautological condition ('total >= 100 or total > 0') and weak tests. Mutation testing revealed that relational operator inversions survive undetected (Score: 0.28).",
        "file_path": "pricing/discount_calculator.py",
        "diff": """--- a/pricing/discount_calculator.py
+++ b/pricing/discount_calculator.py
@@ -10,7 +10,10 @@
 def calculate_bulk_discount(total: float, tier: str) -> float:
-    return 0.0
+    # SEMANTIC BUG: Tautology makes '> 0' dominate; mutant total <= 100 survives
+    if total >= 100.0 or total > 0:
+        return total * 0.15
+    return 0.0
""",
        "technical_verdict": "REJECTED",
        "release_policy": "REVIEW",
        "risk_level": "MEDIUM",
        "execution_tier": "DEEP",
        "duration_ms": 1650,
        "criteria": {
            "C1_syntax": {
                "name": "C1: Syntax & AST Integrity",
                "status": "PASS",
                "score": 1.0,
                "detail": "Valid syntax."
            },
            "C2_visible_tests": {
                "name": "C2: Visible Acceptance Tests",
                "status": "PASS",
                "score": 1.0,
                "detail": "Visible tests passed (weak assertions only tested total=150)."
            },
            "C3_hidden_invariants": {
                "name": "C3: Hidden Invariants & Edge Cases",
                "status": "PASS",
                "score": 1.0,
                "detail": "Basic invariants passed."
            },
            "C4_regression": {
                "name": "C4: Regression Suite",
                "status": "PASS",
                "score": 1.0,
                "detail": "Regression suite passed."
            },
            "C5_mutation": {
                "name": "C5: Mutation Resistance",
                "status": "FAIL",
                "score": 0.28,
                "detail": "MUTATION SCORE: 28.6% (2/7 mutants killed, threshold 50.0%). 5 mutants survived, indicating vacuous assertions and weak semantic verification."
            },
            "C6_security": {
                "name": "C6: Security AST & Taint Scan",
                "status": "PASS",
                "score": 1.0,
                "detail": "Security scan passed."
            }
        },
        "mlverify": {
            "mode": "SHADOW_MODE_ONLY",
            "defect_risk": 0.654,
            "risk_band": "MEDIUM",
            "recommended_tier": "DEEP",
            "confidence": 0.821,
            "shadow_agreement": True,
            "explanation": "Flagged elevated risk due to compound boolean expressions with overlapping relational intervals and sparse assertion coverage."
        },
        "events": [
            {"stage": "INITIALIZE", "message": "Verification worker spawned in isolated sandbox environment", "ms_offset": 50},
            {"stage": "INDEXING", "message": "Analyzing repository diff: pricing/discount_calculator.py (+4, -1)", "ms_offset": 120},
            {"stage": "C1_SYNTAX", "message": "AST validation passed: valid Python syntax", "ms_offset": 240},
            {"stage": "C2_TESTS", "message": "Running acceptance unit tests... 2 PASSED (Weak Assertions)", "ms_offset": 530},
            {"stage": "C3_INVARIANTS", "message": "Checking boundary invariants... PASSED", "ms_offset": 810},
            {"stage": "C4_REGRESSION", "message": "Running regression suite... 14 PASSED", "ms_offset": 1040},
            {"stage": "C5_MUTATION", "message": "MUTATION DEFECT: 5/7 mutants survived! Mutation score: 0.28 < 0.50 threshold", "ms_offset": 1490},
            {"stage": "C6_SECURITY", "message": "Security AST visitor: Clean", "ms_offset": 1570},
            {"stage": "MLVERIFY_SHADOW", "message": "MLVerify shadow prediction: Defect Risk 65.4% [MEDIUM], recommends DEEP", "ms_offset": 1600},
            {"stage": "POLICY_GATE", "message": "Decision: REJECTED | Release Policy: REVIEW (Mutation Resistance Failed)", "ms_offset": 1650}
        ]
    }
}


def build_scenario_report(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Generates an audit report structure for a demo scenario."""
    diff_hash = hashlib.sha256(scenario["diff"].encode("utf-8")).hexdigest()
    now_iso = "2026-09-27T20:00:00Z"

    return {
        "report_id": f"rep_{scenario['id']}_{diff_hash[:8]}",
        "timestamp": now_iso,
        "scenario_id": scenario["id"],
        "title": scenario["title"],
        "file_path": scenario["file_path"],
        "diff_sha256": diff_hash,
        "decision": {
            "technical_verdict": scenario["technical_verdict"],
            "release_policy": scenario["release_policy"],
            "risk_level": scenario["risk_level"],
            "criteria_summary": {k: v["status"] for k, v in scenario["criteria"].items()}
        },
        "criteria": scenario["criteria"],
        "mlverify": scenario["mlverify"],
        "telemetry": {
            "duration_ms": scenario["duration_ms"],
            "tier": scenario["execution_tier"],
            "sandbox_used": True,
            "isolation_level": "sandboxed-container"
        }
    }
