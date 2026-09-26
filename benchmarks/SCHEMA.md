# AegisBench Task Specification & Provenance Schema

To prevent benchmark leakage, data contamination, and evaluation bias (as addressed in SWE-Bench Pro Verified and SWE-Serve), every benchmark task in AegisBench enforces strict separation between the **Public Agent Workspace** and the **Private Evaluator Harness**.

---

## Task Directory Layout

```text
task_id/
├── PUBLIC (Exposed to Autonomous Coding Agent)
│   ├── problem.md            # Problem description, requirements, and error context
│   ├── metadata.json         # Task metadata (bug_id, category, difficulty)
│   ├── buggy/                # Isolated repository snapshot containing the defect
│   └── tests/                # Visible test suite provided to the agent
│       └── test_solution.py
│
└── PRIVATE (Retained exclusively by Aegis Evaluator — Never exposed to agent)
    ├── provenance.json       # Ground-truth source repository, commit SHA, and verified issue
    ├── constraints.yaml      # Non-functional constraints (API stability, latency, memory)
    ├── hidden_tests/         # Hidden functional & regression test suite
    │   └── test_hidden.py
    └── oracle_patch.diff     # Gold standard verified human patch
```

---

## Canonical Schemas

### 1. `metadata.json` (Public)
```json
{
  "bug_id": "bug_001_wrong_operator",
  "category": "operator_error",
  "difficulty": "easy",
  "description": "Fix arithmetic precedence in calculation engine",
  "expected_behavior": "Returns mathematically correct order of operations",
  "tags": ["arithmetic", "precedence", "unit-test"]
}
```

### 2. `provenance.json` (Private Evaluator)
```json
{
  "source": "curated_open_source",
  "repository": "https://github.com/aegis-verifier/aegis-benchmarks",
  "base_commit": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "issue_id": "#104",
  "license": "MIT",
  "verified_by": "aegis_verification_suite",
  "verification_status": "reproduced"
}
```

### 3. `constraints.yaml` (Private Evaluator)
```yaml
constraints:
  public_api_unchanged: true
  max_files_modified: 2
  forbidden_modules:
    - subprocess
    - socket
    - pty
  max_latency_regression_pct: 10.0
```

---

## Automated Validation

The benchmark suite is validated using:
```bash
python -m aegis.cli benchmark --dir benchmarks/dev --validate
```
Tasks must pass syntactic validation of source code, have runnable visible tests, and maintain private evaluator separation.
